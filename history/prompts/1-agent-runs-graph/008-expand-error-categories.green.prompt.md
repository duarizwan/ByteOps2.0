---
id: 008
title: Expand Error Categories for Chat Classification
stage: green
date: 2026-05-31
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: dua.rizwan@jonasclub.com
command: Task 1 - Expand error categories (action-center-types.ts, classify-error.ts)
labels: ["error-classification","types","classify-error","action-center","chat"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/lib/action-center-types.ts
  - frontend/src/lib/classify-error.ts
tests:
  - npx tsc --noEmit (no errors in changed files or consumers)
---

## Prompt

You are implementing Task 1: Expand error categories.

Step 1: Add new error categories to the type union in `frontend/src/lib/action-center-types.ts` line 8.
Replace `"auth" | "timeout" | "unknown"` with `"auth" | "timeout" | "oauth_missing" | "no_results" | "mcp_unavailable" | "backend_down" | "unknown"`.

Step 2: Replace entire `frontend/src/lib/classify-error.ts` with expanded regex patterns:
- OAUTH_RE before AUTH_RE (oauth errors may also contain auth keywords)
- NO_RESULTS_RE for empty result detection
- MCP_RE for MCP/tool unavailability detection
- backend_down is NOT detected by classifyError (set in outer catch in chat-interface.tsx)

Step 3: Verify TypeScript compiles cleanly (no errors in changed/consumer files).
Step 4: Commit.

## Response snapshot

Both files updated exactly as specified. TypeScript check (`npx tsc --noEmit`) produced zero errors in any of the changed files or their consumers (`needs-fixing-card.tsx`, `action-center.tsx`, `filter-tabs.tsx`, `summarize-action.ts`). All pre-existing errors are in `tests/` directory and are unrelated (missing `@types/jest` — a pre-existing setup issue). Committed as `9d0347d`.

## Outcome

- Impact: ActionErrorCategory type union expanded from 3 to 7 members; classifyError gains 3 new regex patterns with correct priority ordering (oauth before auth); purely additive change, no existing consumers broken.
- Tests: TypeScript noEmit passed for all source files; pre-existing test-file TS2582 errors unchanged.
- Files: frontend/src/lib/action-center-types.ts, frontend/src/lib/classify-error.ts
- Next prompts: Task 2 (chat stage labels in assistant bubble), Task 3 (graceful error states using new categories)
- Reflection: Straightforward additive change. Pre-existing tsc errors in tests/ directory are a known setup gap (no @types/jest configured) that predates this task.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): tsc --noEmit PASS (source files only)
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): Task 2 - add stage labels to assistant bubble in chat-interface.tsx
