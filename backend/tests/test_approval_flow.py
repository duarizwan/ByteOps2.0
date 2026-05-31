import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

def test_read_tool_no_approval():
    from app.services.agent_policy import classify_tool_call, requires_approval
    assert not requires_approval(classify_tool_call("gmail", "search_emails"))

def test_send_tool_requires_approval():
    from app.services.agent_policy import classify_tool_call, requires_approval
    d = classify_tool_call("gmail", "send_email")
    assert requires_approval(d)
    assert d.risk.value == "external_send"

def test_destructive_tool_requires_approval():
    from app.services.agent_policy import classify_tool_call, requires_approval
    d = classify_tool_call("gmail", "trash_email")
    assert requires_approval(d)
    assert d.risk.value == "destructive"

def test_resolve_approval_unknown_run_returns_false():
    from app.services.agent_runtime import resolve_approval
    assert resolve_approval(str(uuid4()), approved=True) is False

@pytest.mark.asyncio
async def test_policy_aware_call_tool_read_executes_immediately():
    from app.services.agent_runtime import policy_aware_call_tool
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(type="text", text="results")]
    session.call_tool = AsyncMock(return_value=mock_result)
    block = MagicMock()
    block.name = "search_emails"
    block.input = {"query": "inbox"}
    queue = asyncio.Queue()
    result = await policy_aware_call_tool(session, block, "gmail", None, None, queue)
    assert result == "results"
    session.call_tool.assert_called_once_with("search_emails", arguments={"query": "inbox"})

@pytest.mark.asyncio
async def test_policy_aware_call_tool_write_no_db_executes_immediately():
    from app.services.agent_runtime import policy_aware_call_tool
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(type="text", text="sent")]
    session.call_tool = AsyncMock(return_value=mock_result)
    block = MagicMock()
    block.name = "send_email"
    block.input = {"to": "a@b.com", "subject": "Hi"}
    queue = asyncio.Queue()
    result = await policy_aware_call_tool(session, block, "gmail", None, None, queue)
    assert result == "sent"
    session.call_tool.assert_called_once()


@pytest.mark.asyncio
async def test_policy_aware_call_tool_registers_approval_gate_before_prompting_user():
    from app.services.agent_runtime import policy_aware_call_tool, resolve_approval

    run_id = uuid4()
    status_updates = []

    class FakeExecuteResult:
        pass

    class FakeDb:
        async def execute(self, statement):
            status_updates.append(str(statement))
            return FakeExecuteResult()

        async def commit(self):
            return None

        def add(self, entity):
            return None

        async def refresh(self, entity):
            return None

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.content = [MagicMock(type="text", text="sent")]
    session.call_tool = AsyncMock(return_value=mock_result)
    block = MagicMock()
    block.name = "send_email"
    block.input = {"to": "person@example.com", "subject": "Hi", "body": "Hello"}
    queue = asyncio.Queue()

    task = asyncio.create_task(policy_aware_call_tool(session, block, "gmail", run_id, FakeDb(), queue))
    approval_event = await asyncio.wait_for(queue.get(), timeout=1)

    assert approval_event[0] == "approval_required"
    assert status_updates
    assert resolve_approval(str(run_id), approved=True) is True
    result = await asyncio.wait_for(task, timeout=1)

    assert result == "sent"
    session.call_tool.assert_called_once_with("send_email", arguments=block.input)


@pytest.mark.asyncio
async def test_approve_agent_run_accepts_active_gate_when_status_is_stale(monkeypatch):
    from app.api.agent_runs import approve_agent_run
    from app.models.agent_run import AgentRunStatus

    run_id = uuid4()
    user_id = uuid4()
    run = SimpleNamespace(id=run_id, user_id=user_id, status=AgentRunStatus.RUNNING)

    class RunResult:
        def scalar_one_or_none(self):
            return run

    class FakeDb:
        async def execute(self, statement):
            return RunResult()

    monkeypatch.setattr("app.api.agent_runs.resolve_approval", lambda run_id, approved: True)

    result = await approve_agent_run(run_id, SimpleNamespace(id=user_id), FakeDb())

    assert result == {"status": "approved", "run_id": str(run_id)}
