---
id: 002
title: UI Polish Implementation Plan — All 4 Features
stage: plan
date: 2026-05-31
surface: agent
model: claude-sonnet-4-6
feature: 2-ui-polish
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /superpowers:writing-plans
labels: ["ui-polish","plan","chat-feedback","status-badges","error-states","loading-transitions"]
links:
  spec: specs/2-ui-polish/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - docs/superpowers/plans/2026-05-31-ui-polish.md
  - history/prompts/2-ui-polish/002-ui-polish-plan.plan.prompt.md
tests:
  - none (plan stage)
---

## Prompt

Write the design doc and move to implementation plan for 4 UI polish items:
1. Chat progress feedback (inline assistant bubble, Option A chosen)
2. Activity status badges + prominent trace button
3. Graceful error states
4. Loading transitions (skeleton + spinner)

## Response snapshot

Implementation plan written to `docs/superpowers/plans/2026-05-31-ui-polish.md`.

**6 tasks, 7 files:**
- Task 1: Expand ActionErrorCategory type + classifyError regex (action-center-types.ts, classify-error.ts)
- Task 2: Chat stage labels — stage field on Message, STAGE_LABELS map, SSE handler updates, render replacement (chat-interface.tsx)
- Task 3: Chat error states — CHAT_ERROR_MESSAGES map, errorClass field on Message, SSE + catch handler, error bubble render (chat-interface.tsx)
- Task 4: ActionCard status badge + trace button — STATUS_BADGE map, badge pill render, styled button (action-card.tsx)
- Task 5: Action Center skeleton — ActionCardSkeleton component, isLoading guard (action-center.tsx)
- Task 6: Trace drawer skeleton — onLoad prop on GraphCanvas, isGraphReady state + spinner overlay in TraceDrawer (graph-canvas.tsx, trace-drawer.tsx)

All 16 functional requirements mapped to tasks. No new API endpoints needed.

## Outcome

- ✅ Impact: Implementation plan ready for execution via subagent-driven-development or executing-plans
- 🧪 Tests: final step runs backend pytest (181 tests) + TypeScript check
- 📁 Files: docs/superpowers/plans/2026-05-31-ui-polish.md
- 🔁 Next prompts: /superpowers:subagent-driven-development or /superpowers:executing-plans
- 🧠 Reflection: FR-013 (input enabled after error) relies on existing isTyping=false in finally block — noted in spec coverage table; no additional change needed.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): spec coverage table — all 16 FRs mapped
- Prompt variant (if applicable): none
- Next experiment: none
