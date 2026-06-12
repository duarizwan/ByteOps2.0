---
id: "002"
title: Agent Runs Graph Tasks
stage: tasks
date: 2026-05-30
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: dua.rizwan@jonasclub.com
command: /sp.tasks
labels: ["tasks","graph","react-flow","dagre","tdd","ellipse-nodes","runs-page"]
links:
  spec: specs/1-agent-runs-graph/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/1-agent-runs-graph/tasks.md (created)
tests:
  - frontend/tests/graph-transformer.test.ts (planned — T004)
  - frontend/tests/ellipse-node.test.tsx (planned — T008)
  - frontend/tests/graph-canvas.test.tsx (planned — T009)
  - frontend/tests/node-detail-popup.test.tsx (planned — T015)
  - frontend/tests/runs-list-panel.test.tsx (planned — T018)
---

## Prompt

continue next step

## Response snapshot

Generated `specs/1-agent-runs-graph/tasks.md` with 29 atomic tasks across 7 phases:

- **Phase 1 (T001–T003)**: Install @xyflow/react + @dagrejs/dagre, scaffold directories
- **Phase 2 (T004–T007)**: graphTransformer TDD (types → failing tests → implementation), useAgentRun hook — BLOCKS all stories
- **Phase 3 (T008–T014)**: US1 — EllipseNode + GraphCanvas + RunsPage + route + sidebar nav icon (MVP)
- **Phase 4 (T015–T017)**: US2 — NodeDetailPopup with click-to-inspect, × close, payload truncation
- **Phase 5 (T018–T021)**: US3 — RunRow dismiss button + RunsListPanel + Clear all + session-state dismiss wiring
- **Phase 6 (T022–T024)**: US4 — CSS var audit, React Flow theme config, ellipse node state verification
- **Phase 7 (T025–T029)**: Polish — zero-step runs, 404 handling, long payload truncation, narrow viewport, auto-select on dismiss

TDD is applied throughout: each user story phase starts with RED tests before implementation tasks.

## Outcome

- ✅ Impact: tasks.md is ready to execute; implementation can begin at T001
- 🧪 Tests: 5 test files planned, written in RED before implementation (TDD mandatory per constitution)
- 📁 Files: tasks.md created at specs/1-agent-runs-graph/tasks.md
- 🔁 Next prompts: Begin implementation — start at T001 (install packages) then T004 (write graphTransformer tests)
- 🧠 Reflection: Tasks are fully mapped to user stories with clear checkpoints after each phase. MVP is achievable at end of Phase 3 (US1 only — graph visible with ellipse nodes).

## Evaluation notes (flywheel)

- Failure modes observed: setup-plan.ps1 and check-prerequisites.ps1 blocked by Windows execution policy; used agent-native flow throughout
- Graders run and results (PASS/FAIL): none yet
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run T001 (npm install) and T004 (write graph-transformer tests)
