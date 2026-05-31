"""Calendar Specialist Agent.

Spawns the Calendar MCP server as a stdio subprocess (one per request),
discovers its tools, and runs a Claude tool-calling loop until the
task is complete. Streams results back via an asyncio.Queue.

Key design decisions:
  - Mirrors gmail_agent.py — same pattern, different tool and env vars.
  - Credentials (access_token, refresh_token, client_id, secret) are
    passed to the subprocess via environment variables so the MCP server
    can perform token refresh if needed.
  - Text tokens are pushed as plain strings (type "delta").
  - Tool activity is pushed as ("tool_call_start", ...) / ("tool_call_result", ...) tuples.
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment

from app.core.config import get_settings
from app.core.llm_client import get_llm_client, TextBlock, ToolUseBlock, RateLimitError
from app.models.tool_connection import ToolConnection
from app.agents.response_format import RESPONSE_FORMAT, PLATFORM_LINKS
from app.services.agent_runtime import policy_aware_call_tool


CALENDAR_SYSTEM_PROMPT = """\
You are the ByteOps Calendar Specialist. You have tools to read, search, create, update,
and delete calendar events on behalf of the user.

Guidelines:
- Always act on the user's intent directly; do not narrate what you are about to do.
- When listing events, be concise: title, date/time, location (if present), and attendees.
- For time range queries, default to listing events for the next 7 days if no range is specified.
- When attendees are added to an event, Google Calendar automatically emails them the invite (sendUpdates="all"). Simply confirm the event was created — do not add disclaimers about custom email or email sending capabilities.

Datetime format rules (CRITICAL — follow exactly):
- Use ISO 8601 format WITHOUT timezone offset: '2025-06-01T10:00:00' (no +05:00, no Z suffix)
- Always pass the 'timezone' parameter separately using IANA names: 'Asia/Karachi', 'America/New_York',
  'Europe/London', 'UTC', etc. Default to 'UTC' if the user doesn't specify.
- For all-day events, use date-only format: '2025-06-01' (no time component)
- For list/search time bounds, use UTC with Z suffix: '2025-06-01T00:00:00Z'
- Use quick_add for natural-language scheduling like "lunch tomorrow at 1pm" — it's the fastest tool.

Confirmation rules:
- For create_event: confirm title, date/time, and timezone with user before calling.
- For delete_event and update_event: always confirm full details before calling.

If a tool returns a permission error (403), tell the user:
  "Your Calendar connection needs to be reconnected with full access. Please go to
   Settings → Connections, disconnect Calendar, and reconnect it."
""" + RESPONSE_FORMAT + PLATFORM_LINKS


async def run_calendar_agent(
    user_message: str,
    history: list[dict],
    tool_connection: ToolConnection,
    queue: asyncio.Queue,
    run_id=None,
    db=None,
) -> str:
    """Run the Calendar specialist agent.

    Args:
        user_message:     The latest user message.
        history:          Full conversation history in OpenAI message format.
        tool_connection:  The user's ToolConnection record (contains tokens).
        queue:            SSE event queue shared with chat.py's consumer.

    Returns the final assistant text response.
    """
    settings = get_settings()
    llm = get_llm_client()

    # ── Build environment for the MCP subprocess ──────────────────────────────
    env = get_default_environment()
    env["CALENDAR_ACCESS_TOKEN"] = tool_connection.access_token
    if tool_connection.refresh_token:
        env["CALENDAR_REFRESH_TOKEN"] = tool_connection.refresh_token
    env["CALENDAR_CLIENT_ID"] = settings.calendar_client_id
    env["CALENDAR_CLIENT_SECRET"] = settings.calendar_client_secret

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_servers.calendar.server"],
        env=env,
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                # ── Discover MCP tools and convert to Claude schema ───────────
                result = await session.list_tools()
                claude_tools = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.inputSchema,
                    }
                    for t in result.tools
                ]

                # ── Build messages: history (user/assistant only) ─────────────
                messages: list[dict] = [
                    m for m in history if m["role"] in ("user", "assistant")
                ]
                if not messages or messages[-1].get("content") != user_message:
                    messages.append({"role": "user", "content": user_message})

                # ── Agentic tool-calling loop ─────────────────────────────────
                while True:
                    for attempt in range(3):
                        try:
                            response = await llm.create_message(
                                messages=messages,
                                system=CALENDAR_SYSTEM_PROMPT,
                                max_tokens=8192,
                                tools=claude_tools if claude_tools else None,
                            )
                            break
                        except RateLimitError:
                            if attempt < 2:
                                await asyncio.sleep(2 if attempt == 0 else 5)
                            else:
                                raise

                    text_content = ""
                    tool_use_blocks = []
                    for block in response.content:
                        if isinstance(block, TextBlock):
                            text_content += block.text
                        elif isinstance(block, ToolUseBlock):
                            tool_use_blocks.append(block)

                    if text_content:
                        await queue.put(text_content)

                    llm.append_response(messages, response)

                    if not tool_use_blocks:
                        return text_content or ""

                    tool_results = []
                    for block in tool_use_blocks:
                        result_text = await policy_aware_call_tool(
                            session, block, "calendar", run_id, db, queue
                        )
                        tool_results.append({"tool_use_id": block.id, "content": result_text})

                    llm.append_tool_results(messages, tool_results)

        return "Done."
    except BaseExceptionGroup as eg:
        exc: BaseException = eg
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise RuntimeError(str(exc)) from exc
