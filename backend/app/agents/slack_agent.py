"""Slack Specialist Agent.

Spawns the Slack MCP server as a stdio subprocess (one per request),
discovers its tools, and runs a Claude tool-calling loop until the
task is complete. Streams results back via an asyncio.Queue.

Slack uses a bot token (no refresh cycle required) so the MCP subprocess
only needs SLACK_BOT_TOKEN.
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

_slack_llm: anthropic.AsyncAnthropic | None = None


def _get_slack_llm() -> anthropic.AsyncAnthropic:
    global _slack_llm
    if _slack_llm is None:
        settings = get_settings()
        _slack_llm = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    return _slack_llm


SLACK_SYSTEM_PROMPT = """\
You are the ByteOps Slack Specialist. You have tools to read channels, messages, threads, \
send messages, DMs, manage reactions, and list users.

Guidelines:
- Act on the user's intent directly; do not narrate what you are about to do.
- When listing channels or messages, be concise: name/user and key content.
- For send_message and send_dm, always confirm the content and recipient with the user before \
calling the tool unless they have already explicitly confirmed.
- For delete_message and update_message, always confirm with the user first.
- If a tool returns an error (e.g., missing scope), explain it and suggest reconnecting Slack \
in Settings → Connections with the required scopes.
""" + RESPONSE_FORMAT


async def run_slack_agent(
    user_message: str,
    history: list[dict],
    tool_connection: ToolConnection,
    queue: asyncio.Queue,
) -> str:
    """Run the Slack specialist agent."""
    llm = _get_slack_llm()

    env = get_default_environment()
    env["SLACK_BOT_TOKEN"] = tool_connection.access_token

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_servers.slack.server"],
        env=env,
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.list_tools()
                claude_tools = [
                    {
                        "name": t.name,
                        "description": t.description,
                        "input_schema": t.inputSchema,
                    }
                    for t in result.tools
                ]

                messages: list[dict] = [
                    m for m in history if m["role"] in ("user", "assistant")
                ]
                if not messages or messages[-1].get("content") != user_message:
                    messages.append({"role": "user", "content": user_message})

                while True:
                    for attempt in range(3):
                        try:
                            response = await llm.messages.create(
                                model=CLAUDE_MODEL,
                                max_tokens=8192,
                                system=SLACK_SYSTEM_PROMPT,
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

                    if text_content:
                        await queue.put(text_content)

                    messages.append({"role": "assistant", "content": response.content})

                    if not tool_use_blocks:
                        return text_content or ""

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

                    messages.append({"role": "user", "content": tool_results})

        return "Done."
    except BaseExceptionGroup as eg:
        exc: BaseException = eg
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise RuntimeError(str(exc)) from exc
