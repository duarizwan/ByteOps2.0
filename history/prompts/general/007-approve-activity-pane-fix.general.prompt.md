---
id: 007
title: Approve Activity Pane Fix
stage: general
date: 2026-05-29
surface: agent
model: GPT-5 Codex
feature: none
branch: none
user: rizwadua
command: approved
labels: ["frontend","backend","activity-pane","tdd"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/dashboard/context-panel.tsx
  - frontend/tests/context-panel.test.tsx
  - backend/app/api/chat.py
  - backend/tests/test_chat_activity_notification.py
  - history/prompts/general/007-approve-activity-pane-fix.general.prompt.md
tests:
  - npm run test:run -- tests/context-panel.test.tsx
  - backend/.venv/Scripts/python.exe -m pytest tests/test_chat_activity_notification.py
  - npm run test:run
  - backend/.venv/Scripts/python.exe -m pytest
---

## Prompt

approved

## Response snapshot

Implemented the approved activity pane fix with tests. The ContextPanel now routes task-like Gmail/Slack/any-platform items into Tasks, keeps those out of Alerts, and displays extracted attention titles and derived priorities instead of raw chat queries. Chat-created backend notifications now build an extracted activity payload with category, action-required flag, attention title, extracted priority, and original user query stored only in metadata.

## Outcome

- ✅ Impact: Activity pane routing now separates alerts from tasks and avoids using raw user prompts as visible alert titles.
- 🧪 Tests: focused frontend and backend tests pass; broader suites still have unrelated pre-existing failures.
- 📁 Files: modified ContextPanel, ContextPanel tests, chat API activity payload logic, backend payload tests, and this PHR.
- 🔁 Next prompts: resolve unrelated existing test failures in chat-interface avatar expectations, calendar MCP expectations, and Jira/Dropbox response-format tests.
- 🧠 Reflection: Metadata-first classification keeps the API contract stable while allowing extracted Gmail, Slack, and other tool items to land in the right pane.

## Evaluation notes (flywheel)

- Failure modes observed: Full test suites contain unrelated failures outside the activity-pane changes.
- Graders run and results (PASS/FAIL): focused ContextPanel PASS; focused backend activity notification PASS; full frontend FAIL due chat-interface avatar test; full backend FAIL due calendar and response-format expectation drift.
- Prompt variant (if applicable): null.
- Next experiment (smallest change to try): clean up existing unrelated tests or align them with current implementation in a separate task.
