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

import anthropic
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment

from app.core.config import get_settings
from app.models.tool_connection import ToolConnection
from app.agents.response_format import RESPONSE_FORMAT

CLAUDE_MODEL = "claude-sonnet-4-6"

# Module-level client — created once, reused for all Calendar agent requests
_calendar_llm: anthropic.AsyncAnthropic | None = None


def _get_calendar_llm() -> anthropic.AsyncAnthropic:
    """Return (or lazily create) the shared Calendar AsyncAnthropic client."""
    global _calendar_llm
    if _calendar_llm is None:
        settings = get_settings()
        _calendar_llm = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    return _calendar_llm


CALENDAR_SYSTEM_PROMPT = """\
You are the ByteOps Calendar Specialist. You have tools to read, search, create, update,
and delete calendar events on behalf of the user.

Guidelines:
- Always act on the user's intent directly; do not narrate what you are about to do.
- When listing events, be concise: title, date/time, location (if present), and attendees.
- For time range queries, default to listing events for the next 7 days if no range is specified.

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
""" + RESPONSE_FORMAT


async def run_calendar_agent(
    user_message: str,
    history: list[dict],
    tool_connection: ToolConnection,
    queue: asyncio.Queue,
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
    llm = _get_calendar_llm()

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
                            response = await llm.messages.create(
                                model=CLAUDE_MODEL,
                                max_tokens=8192,
                                system=CALENDAR_SYSTEM_PROMPT,
                                messages=messages,
                                tools=claude_tools if claude_tools else anthropic.NOT_GIVEN,
                            )
                            break
                        except anthropic.RateLimitError:
                            if attempt < 2:
                                await asyncio.sleep(20)
                            else:
                                raise

                    # Extract text and tool_use blocks from response
                    text_content = ""
                    tool_use_blocks = []
                    for block in response.content:
                        if block.type == "text":
                            text_content += block.text
                        elif block.type == "tool_use":
                            tool_use_blocks.append(block)

                    # Stream any text content to the client
                    if text_content:
                        await queue.put(text_content)

                    # Append assistant message (content blocks preserved for tool_use context)
                    messages.append({"role": "assistant", "content": response.content})

                    # Exit: no more tool calls requested
                    if not tool_use_blocks:
                        return text_content or ""

                    # Execute each tool call via MCP and collect results
                    tool_results = []
                    for block in tool_use_blocks:
                        await queue.put(("tool_call_start", block.name, json.dumps(block.input)))

                        tool_result = await session.call_tool(block.name, arguments=block.input)
                        result_text = "\n".join(
                            c.text for c in tool_result.content if c.type == "text"
                        )

                        await queue.put(("tool_call_result", block.name, result_text))

                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_text,
                        })

                    # Feed all tool results back to Claude in a single user message
                    messages.append({"role": "user", "content": tool_results})

        return "Done."
    except BaseExceptionGroup as eg:
        exc: BaseException = eg
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise RuntimeError(str(exc)) from exc
