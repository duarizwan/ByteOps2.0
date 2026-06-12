---
id: "002"
title: Add Inline Two-Click Delete WorkflowCard
stage: green
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: agent-runs-graph
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.phr
labels: ["workflow", "delete", "inline-confirm", "WorkflowCard", "context-panel", "testing"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/dashboard/context-panel.tsx
  - frontend/tests/workflow-card-delete.test.tsx
tests:
  - frontend/tests/workflow-card-delete.test.tsx (4 tests, all PASS)
---

## Prompt

title="add inline two-click delete WorkflowCard" stage=green feature=agent-runs-graph

## Response snapshot

Implemented Task 2: inline two-click delete on `WorkflowCard`. Created the test file first (4 tests, all passing with inline component logic). Then updated `context-panel.tsx`: added `onDelete` prop + `confirmDelete` state + `handleDeleteClick` + outside-click `useEffect` to `WorkflowCard`; added the delete button with conditional destructive styling after the Details button; added `Trash2` and `Sparkles` to the lucide-react import; wired `deleteWorkflow` from `useWorkflows()` into the parent render. Committed as `feat: add inline two-click delete to WorkflowCard`. Full test run: 8 pre-existing failures, 0 new failures introduced.

## Outcome

- ✅ Impact: WorkflowCard now has a two-click inline delete: first click shows "Confirm delete?" in destructive styling; second click calls `onDelete`; clicking outside resets to "Delete".
- 🧪 Tests: 4/4 pass in `workflow-card-delete.test.tsx`; full suite shows 198 passing, 8 pre-existing failures, 0 new regressions.
- 📁 Files: `frontend/src/components/dashboard/context-panel.tsx` (modified), `frontend/tests/workflow-card-delete.test.tsx` (created)
- 🔁 Next prompts: Task 3 — Add WorkflowSuggestionModal component; Task 4 — Wire "Generate with AI" button into workflow tab.
- 🧠 Reflection: Writing the inline test component before touching production code made the logic contract explicit and the tests deterministic; the outside-click handler is isolated per card via `workflow.id`-scoped element ID.

## Evaluation notes (flywheel)

- Failure modes observed: Script `.specify/scripts/bash/create-phr.sh` not found; fell back to agent-native file write using template. No other issues.
- Graders run and results (PASS/FAIL): Manual review — all placeholders resolved, routing correct (feature stage → history/prompts/agent-runs-graph/), PROMPT_TEXT preserved verbatim.
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): Add the missing create-phr.sh script or a Windows-compatible equivalent so the shell path works on this platform.
