---
id: 014
title: Fix useWorkflows deleteWorkflow renderHook Tests
stage: green
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: none
branch: 1-agent-runs-graph
user: dua.rizwan@jonasclub.com
command: fix use-workflows-delete.test.ts to use renderHook
labels: ["testing","react-hooks","vitest","renderHook","useWorkflows"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/tests/use-workflows-delete.test.ts
tests:
  - frontend/tests/use-workflows-delete.test.ts
---

## Prompt

Fix the test file `frontend/tests/use-workflows-delete.test.ts`. The current tests test a standalone reimplementation rather than the actual `useWorkflows` hook. Requirements:
1. Test that state is actually removed when DELETE succeeds
2. Test that DELETE is called with the correct URL and auth header
3. Test that state is NOT changed when DELETE fails

Tests must use `renderHook(() => useWorkflows())` to render the actual hook and check its `.current.workflows` state.

## Response snapshot

Replaced the entire test file with `renderHook`-based tests. Root cause investigation revealed two issues:

1. The `waitFor` timeout was caused by an infinite re-render loop: the mock `useAuth: () => ({ getToken: async () => "test-token" })` created a new `getToken` arrow function on every render call, causing `useCallback([getToken])` in the hook to recreate `fetch_` on every render, which triggered `useEffect([fetch_])` to re-run, calling `setIsLoading(true)` and causing another render. Fixed by hoisting `stableGetToken` outside the mock factory so it has a stable reference.

2. After fixing the infinite loop, the polling `setInterval` (30s) would fire during `waitFor` and consume mock responses intended for the DELETE call. Fixed by using `find()` on `fetchMock.mock.calls` to locate the specific DELETE call rather than relying on positional index.

All 3 tests pass in ~274ms.

## Outcome

- Impact: Tests now exercise the real `useWorkflows` hook via `renderHook`, verifying actual state management for `deleteWorkflow`
- Tests: 3 passing — removes workflow on success, calls DELETE with correct URL/auth, preserves state on failure
- Files: frontend/tests/use-workflows-delete.test.ts rewritten (83 insertions, 61 deletions)
- Next prompts: Task 2 — add inline delete button to WorkflowCard
- Reflection: The infinite re-render loop from unstable mock function references is a subtle but common React testing footgun; using a module-level stable reference is the clean fix

## Evaluation notes (flywheel)

- Failure modes observed: (1) infinite re-render from unstable getToken mock reference; (2) polling interval consuming mock responses before deleteWorkflow was called
- Graders run and results (PASS/FAIL): npx vitest run tests/use-workflows-delete.test.ts — PASS (3/3)
- Prompt variant (if applicable): null
- Next experiment: Consider adding vi.hoisted pattern to CLAUDE.md as a testing guideline for hooks with useAuth dependencies
