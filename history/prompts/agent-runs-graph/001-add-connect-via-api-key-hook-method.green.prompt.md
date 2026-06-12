---
id: "001"
title: add connectViaApiKey to useToolConnections hook
stage: green
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: agent-runs-graph
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.phr
labels: ["hook", "frontend", "tool-connections", "api-key", "tdd", "vitest"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/hooks/use-tool-connections.ts
  - frontend/tests/tool-connections.test.tsx
tests:
  - frontend/tests/tool-connections.test.tsx — connectViaApiKey describe block (2 tests)
---

## Prompt

Task 2: add connectViaApiKey to useToolConnections hook

## Response snapshot

Read the existing test file and hook implementation, then added two isolated `connectViaApiKey` tests (following the existing standalone-function pattern to avoid OOM from polling timers), added the `connectViaApiKey` `useCallback` method to `use-tool-connections.ts` (after `disconnect`, before `isConnected`), added it to the return object, verified all 7 tests pass, and committed.

## Outcome

- Impact: `useToolConnections` now exposes `connectViaApiKey(tool, credentials)` which POSTs to `/api/auth/{tool}/connect-apikey` with a Bearer token, throws on non-ok responses, and refreshes connections on success. Two new tests cover the happy path and error path.
- Tests: 7/7 passed in `frontend/tests/tool-connections.test.tsx` (5 pre-existing + 2 new).
- Files: `frontend/src/hooks/use-tool-connections.ts` (added method + updated return), `frontend/tests/tool-connections.test.tsx` (added standalone helper + 2 tests).
- Next prompts: Task 3 — Frontend tabbed ConnectToolModal that calls `connectViaApiKey`; Task 4 — fix `useToolConnections` mocks in other test files.
- Reflection: The existing test file deliberately avoids `renderHook`/`useAuth` mocking to prevent OOM from the hook's polling timers. New tests must mirror the standalone-function pattern rather than using the task description's `renderHook` approach.

## Evaluation notes (flywheel)

- Failure modes observed: Task description specified `renderHook`/`useAuth` mock tests, but the existing test file uses a standalone-function pattern for memory safety. Adapting to the project's actual pattern was necessary and undocumented in the task.
- Graders run and results (PASS/FAIL): vitest run — PASS (7/7)
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Annotate the test file header with a comment explicitly warning future tasks not to use `renderHook` in this file, to avoid the same adaptation step.
