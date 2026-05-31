"""GitHub Specialist Agent.

Spawns the GitHub MCP server as a stdio subprocess (one per request),
discovers its tools, and runs a Claude tool-calling loop until the
task is complete. Streams results back via an asyncio.Queue.

GitHub uses a single personal access token (no refresh token) so the
MCP subprocess only needs GITHUB_ACCESS_TOKEN.
"""

from __future__ import annotations

import asyncio
import json
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client, get_default_environment

from app.core.llm_client import get_llm_client, TextBlock, ToolUseBlock, RateLimitError
from app.models.tool_connection import ToolConnection
from app.agents.response_format import RESPONSE_FORMAT, PLATFORM_LINKS
from app.services.agent_runtime import policy_aware_call_tool


GITHUB_SYSTEM_PROMPT = """\
You are the ByteOps GitHub Specialist. You have tools to read and write to the
user's GitHub account: repositories, pull requests, issues, comments, and notifications.

Guidelines:
- Always act on the user's intent directly; do not narrate what you are about to do.
- When listing repositories or PRs, be concise: name, status, and relevant metadata.
- For 'open PRs', first call list_repos to know what repos to check, then list_prs
  for the most recently active ones.
- If a tool returns an error (e.g., 404 for unknown repo), explain it clearly.
- Never invent repository names or PR numbers.

Write operation rules (create_repo, create_issue, create_pr, merge_pr, close_issue,
update_issue, update_pr, close_pr, comment_on_issue):
- Always confirm the key details with the user before executing any write action.
- For merge_pr: state the repo, PR number, and merge method before calling.
- For create_repo: confirm name and visibility (public/private) before calling.
""" + RESPONSE_FORMAT + PLATFORM_LINKS


async def run_github_agent(
    user_message: str,
    history: list[dict],
    tool_connection: ToolConnection,
    queue: asyncio.Queue,
    run_id=None,
    db=None,
) -> str:
    """Run the GitHub specialist agent."""
    llm = get_llm_client()

    env = get_default_environment()
    env["GITHUB_ACCESS_TOKEN"] = tool_connection.access_token

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "app.mcp_servers.github.server"],
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
                            response = await llm.create_message(
                                messages=messages,
                                system=GITHUB_SYSTEM_PROMPT,
                                max_tokens=8192,
                                tools=claude_tools if claude_tools else None,
                            )
                            break
                        except RateLimitError:
                            if attempt < 2:
                                await asyncio.sleep(20)
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
                            session, block, "github", run_id, db, queue
                        )
                        tool_results.append({"tool_use_id": block.id, "content": result_text})

                    llm.append_tool_results(messages, tool_results)

        return "Done."
    except BaseExceptionGroup as eg:
        exc: BaseException = eg
        while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
            exc = exc.exceptions[0]
        raise RuntimeError(str(exc)) from exc
