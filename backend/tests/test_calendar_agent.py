"""Tests for the Calendar specialist agent: token passing and event emission."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.calendar_agent import run_calendar_agent


class _FakeConnection:
    access_token = "test-access-token"
    refresh_token = "test-refresh-token"


from app.core.llm_client import TextBlock, ToolUseBlock

def _text_block(text: str) -> TextBlock:
    return TextBlock(type="text", text=text)


def _tool_use_block(name: str, tool_id: str, input_: dict) -> ToolUseBlock:
    return ToolUseBlock(type="tool_use", id=tool_id, name=name, input=input_)


def _llm_response(content: list) -> MagicMock:
    r = MagicMock()
    r.content = content
    return r


def _tool_result(text: str) -> MagicMock:
    item = MagicMock()
    item.type = "text"
    item.text = text
    r = MagicMock()
    r.content = [item]
    return r


def _fake_tool(name: str) -> MagicMock:
    t = MagicMock()
    t.name = name
    t.description = f"{name} tool"
    t.inputSchema = {"type": "object", "properties": {}}
    return t


def _make_session_mock() -> AsyncMock:
    session = AsyncMock()
    session.initialize = AsyncMock()
    session.list_tools = AsyncMock(
        return_value=MagicMock(tools=[_fake_tool("list_events"), _fake_tool("search_events")])
    )
    session.call_tool = AsyncMock(return_value=_tool_result("event data"))
    return session


def _fake_settings() -> MagicMock:
    s = MagicMock()
    s.claude_api_key = "test-key"
    s.calendar_client_id = "test-client-id"
    s.calendar_client_secret = "test-client-secret"
    return s


@pytest.mark.anyio
async def test_calendar_agent_passes_tokens_to_subprocess():
    """run_calendar_agent injects Calendar credentials into the subprocess env."""
    conn = _FakeConnection()
    queue: asyncio.Queue = asyncio.Queue()
    captured: dict = {}

    def _capture_params(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    session_mock = _make_session_mock()

    @asynccontextmanager
    async def _fake_stdio(_params):
        yield (None, None)

    @asynccontextmanager
    async def _fake_session(_r, _w):
        yield session_mock

    mock_llm = MagicMock()
    mock_llm.create_message = AsyncMock(
        return_value=_llm_response([_text_block("Here are your events.")])
    )

    with (
        patch("app.agents.calendar_agent.get_default_environment", return_value={}),
        patch("app.agents.calendar_agent.get_settings", return_value=_fake_settings()),
        patch("app.agents.calendar_agent.StdioServerParameters", side_effect=_capture_params),
        patch("app.agents.calendar_agent.stdio_client", _fake_stdio),
        patch("app.agents.calendar_agent.ClientSession", _fake_session),
        patch("app.agents.calendar_agent.get_llm_client", return_value=mock_llm),
    ):
        await run_calendar_agent("What's on my calendar?", [], conn, queue)

    env = captured.get("env", {})
    assert env.get("CALENDAR_ACCESS_TOKEN") == "test-access-token"
    assert env.get("CALENDAR_REFRESH_TOKEN") == "test-refresh-token"
    assert env.get("CALENDAR_CLIENT_ID") == "test-client-id"
    assert env.get("CALENDAR_CLIENT_SECRET") == "test-client-secret"


@pytest.mark.anyio
async def test_calendar_agent_emits_tool_call_events():
    """run_calendar_agent pushes tool_call_start and tool_call_result into the queue."""
    conn = _FakeConnection()
    queue: asyncio.Queue = asyncio.Queue()

    session_mock = _make_session_mock()

    @asynccontextmanager
    async def _fake_stdio(_params):
        yield (None, None)

    @asynccontextmanager
    async def _fake_session(_r, _w):
        yield session_mock

    responses = [
        _llm_response([_tool_use_block("list_events", "id-1", {"time_min": "2025-06-01T00:00:00Z"})]),
        _llm_response([_text_block("Your events: Meeting at 10am.")]),
    ]
    call_count = 0

    async def _create(**_kwargs):
        nonlocal call_count
        resp = responses[call_count]
        call_count += 1
        return resp

    mock_llm = MagicMock()
    mock_llm.create_message = _create

    with (
        patch("app.agents.calendar_agent.get_default_environment", return_value={}),
        patch("app.agents.calendar_agent.get_settings", return_value=_fake_settings()),
        patch("app.agents.calendar_agent.StdioServerParameters", return_value=MagicMock()),
        patch("app.agents.calendar_agent.stdio_client", _fake_stdio),
        patch("app.agents.calendar_agent.ClientSession", _fake_session),
        patch("app.agents.calendar_agent.get_llm_client", return_value=mock_llm),
    ):
        await run_calendar_agent("Show my events", [], conn, queue)

    events = []
    while not queue.empty():
        events.append(await queue.get())

    tuples = [e for e in events if isinstance(e, tuple)]
    event_types = [e[0] for e in tuples]

    assert "tool_call_start" in event_types
    assert "tool_call_result" in event_types

    start = next(e for e in tuples if e[0] == "tool_call_start")
    assert start[1] == "list_events"

    result = next(e for e in tuples if e[0] == "tool_call_result")
    assert result[1] == "list_events"
    assert "event data" in result[2]
