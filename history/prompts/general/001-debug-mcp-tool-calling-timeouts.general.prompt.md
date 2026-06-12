---
id: "001"
title: "Debug MCP Tool Calling Timeouts and Heartbeat Implementation"
stage: "green"
date: "2026-05-31"
surface: "agent"
model: "Gemini 3.5 Flash (High)"
feature: "general"
branch: "master"
user: "rizwadua"
command: "idk why when asking fot any task or action to be performed (eg send email) tool calling are not being made also its taking too long and after waiting it says This took longer than expected. Please try again. debug it deeply and resolve this issue its high priority task"
labels: ["debug", "timeout", "mcp", "sse", "keepalive", "heartbeat", "approval-flow"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/chat.py
  - frontend/src/components/dashboard/chat-interface.tsx
  - backend/tests/test_calendar_agent.py
tests:
  - All 93 backend tests — PASS
---

## Prompt

idk why when asking fot any task or action to be performed (eg send email) tool calling are not being made also its taking too long and after waiting it says This took longer than expected. Please try again. debug it deeply and resolve this issue its high priority task

## Response snapshot

We deeply investigated and discovered that the core issue was a design conflict between the **Human-in-the-Loop Approval Flow** and the aggressive **watchdog idle timeouts** configured in both the backend (30s) and frontend (45s). 

When a write/send/destructive tool call (like sending an email or creating a calendar event) is initiated, the agent correctly classifies it as requiring approval and pauses. It yields an `approval_required` event and waits for up to 5 minutes (300s). However, while waiting for the user to read and click "Approve", no SSE chunks are sent. After 30 seconds, the backend idle watchdog terminated the connection and cancelled the task. After 45 seconds, the frontend watchdog aborted the fetch request, displaying "This took longer than expected. Please try again." Because the request was dead, the user's subsequent approval POST had no running agent to resolve, preventing tool execution.

We resolved this by:
1. Adding a `"ping"` keep-alive heartbeat in backend `chat.py` so that if the watchdog fires but the underlying task is still active (e.g. paused for approval or executing slow MCP tools), it yields a `"ping"` event and continues waiting instead of prematurely aborting.
2. Updating frontend `chat-interface.tsx` to detect `approval_required` and `workflow_draft` events, extending the idle watchdog timeout to 5 minutes (300,000ms) to match the backend approval timeout.
3. Fixing stale mocks in `tests/test_calendar_agent.py` to use real `TextBlock` and `ToolUseBlock` classes, bringing the entire backend test suite (93/93 tests) to a 100% passing state.

## Outcome

- ✅ Impact: Resolved the system-wide tool execution timeout bug during approval stages. Users can now seamlessly receive approval dialogs and approve them at their leisure.
- 🧪 Tests: 93/93 backend tests passed successfully
- 📁 Files: `backend/app/api/chat.py`, `frontend/src/components/dashboard/chat-interface.tsx`, `backend/tests/test_calendar_agent.py`
- 🔁 Next prompts: Continue monitoring E2E tool execution stability.
- 🧠 Reflection: Aggressive watchdogs must always be relaxed or augmented with keep-alives during expected human-in-the-loop pauses.

## Evaluation notes (flywheel)

- Failure modes observed: Hardcoded watchdogs clash with human wait times. Stale MagicMocks failing isinstance check in pytest.
- Graders run and results (PASS/FAIL): PASS
- Prompt variant (if applicable): None
- Next experiment (smallest change to try): Add a test that verifies the backend watchdog doesn't abort while the chat task is alive.
