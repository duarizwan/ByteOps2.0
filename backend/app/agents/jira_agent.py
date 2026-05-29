"""Jira Specialist Agent.

Spawns the Jira MCP server as a stdio subprocess (one per request),
discovers its tools, and runs a Claude tool-calling loop until the
task is complete. Streams results back via an asyncio.Queue.

Jira Cloud uses an OAuth2 access token together with a Cloud ID that
identifies the Atlassian cloud instance. Both are injected into the
MCP subprocess via environment variables.
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

_jira_llm: anthropic.AsyncAnthropic | None = None


def _get_jira_llm() -> anthropic.AsyncAnthropic:
    global _jira_llm
    if _jira_llm is None:
        settings = get_settings()
        _jira_llm = anthropic.AsyncAnthropic(api_key=settings.claude_api_key)
    return _jira_llm


JIRA_SYSTEM_PROMPT = """\
You are the ByteOps Jira Specialist. You have tools to manage Jira issues, projects, sprints, and comments.

Guidelines:
- Act on the user's intent directly.
- For create_issue: always confirm project, summary, and type with user unless already specified.
- For transition_issue: first call get_transitions to see valid states, then transition.
- For destructive actions (delete_comment), confirm with user first.
- Use JQL for flexible issue searches: 'project = KEY', 'assignee = currentUser()', \
'status = "In Progress"', 'sprint in openSprints()'.
- If you get a 401/403 error, tell the user to reconnect Jira in Settings → Connections.
""" + RESPONSE_FORMAT


async def run_jira_agent(
    user_message: str,
    history: list[dict],
    tool_connection: ToolConnection,
    queue: asyncio.Queue,
) -> str:
    """Run the Jira specialist agent."""
    llm = _get_jira_llm()

    env = get_default_environment()
    env["JIRA_ACCESS_TOKEN"] = tool_connection.access_token
    env["JIRA_CLOUD_ID"] = (
        tool_connection.metadata_.get("cloud_id", "")
        if tool_connection.metadata_
        else ""
    )

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_servers.jira.server"],
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
                                system=JIRA_SYSTEM_PROMPT,
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
