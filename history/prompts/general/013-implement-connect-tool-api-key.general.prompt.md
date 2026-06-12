---
id: "013"
title: Implement Connect Tool API Key Feature
stage: general
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: connect-tool-api-key
branch: 1-agent-runs-graph
user: Dua Rizwan
command: chat
labels: ["implementation","subagent-driven","api-key","tool-connection","modal","fastapi","react"]
links:
  spec: docs/superpowers/specs/2026-06-02-connect-tool-api-key-design.md
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/oauth.py
  - backend/tests/test_oauth.py
  - frontend/src/hooks/use-tool-connections.ts
  - frontend/tests/tool-connections.test.tsx
  - frontend/src/components/dashboard/collapsible-sidebar.tsx
  - frontend/tests/collapsible-sidebar.test.tsx
tests:
  - backend/tests/test_oauth.py (4 new tests, 11 total passing)
  - frontend/tests/tool-connections.test.tsx (9 tests passing)
  - frontend/tests/collapsible-sidebar.test.tsx (5 tests passing)
---

## Prompt

yes implement it do not use fake emojis either use outlined elements or original icons

## Response snapshot

Executed full subagent-driven development flow across 4 tasks. All 4 tasks completed with spec compliance and code quality reviews passing.

Commits:
- 06c5dfe: feat: add connect-apikey endpoint for GitHub, Jira, Slack, Trello, Dropbox
- c9f5d22: fix: clean up redundant imports and harden oauth apikey error handling
- 03d0b79: feat: add connectViaApiKey method to useToolConnections hook
- f3c2e7d: test: strengthen connectViaApiKey tests
- 6181bb4: feat: replace ConnectToolModal with tabbed API Key / OAuth design
- e66ae27: fix: aria roles, timer cleanup, and chip click navigation in ConnectToolModal

## Outcome

- ✅ Impact: "Connect New Tool" modal now has two tabs — API Key (default) and OAuth (existing). Users can connect GitHub/Jira/Slack/Trello/Dropbox by pasting credentials directly, no OAuth redirect needed.
- 🧪 Tests: 11 backend + 14 frontend tests passing. 3 pre-existing unrelated failures in trace-drawer/action-center.
- 📁 Files: 6 files modified across backend and frontend.
- 🔁 Next prompts: Fix the 3 pre-existing test failures in trace-drawer/action-center. Consider ADR for dual auth method support.
- 🧠 Reflection: Subagent reviews caught disabled chip dead-code path, timer leak, and missing ARIA roles — all fixed before merge.

## Evaluation notes (flywheel)

- Failure modes observed: None critical. Code quality review caught real UX bugs (disabled chip preventing click handler, success timer leak).
- Graders run and results (PASS/FAIL): All spec compliance reviews PASS, all code quality reviews PASS after fixes.
- Prompt variant (if applicable): n/a
- Next experiment: Add Slack/Trello/Dropbox validation tests and upsert-update branch test as follow-up.
