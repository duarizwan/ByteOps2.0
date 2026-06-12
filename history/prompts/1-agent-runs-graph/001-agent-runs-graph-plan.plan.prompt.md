---
id: "001"
title: Agent Runs Graph Plan
stage: plan
date: 2026-05-30
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: dua.rizwan@jonasclub.com
command: /sp.plan
labels: ["plan","graph","react-flow","dagre","runs-page","ellipse-nodes"]
links:
  spec: specs/1-agent-runs-graph/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/1-agent-runs-graph/spec.md (updated — added FR-008a ellipse shape, FR-008b spacing)
  - specs/1-agent-runs-graph/research.md (created)
  - specs/1-agent-runs-graph/data-model.md (created)
  - specs/1-agent-runs-graph/plan.md (created)
tests:
  - none yet (tasks phase next)
---

## Prompt

continue writing and i want the nodes in eclipse shape and the mockup i saw the nodes are too close make it bit distant

## Response snapshot

Updated spec with two new functional requirements:
- FR-008a: nodes must be ellipse (oval) shape, min 160×64px
- FR-008b: min 120px vertical gap, 160px horizontal gap between nodes

Then ran /sp.plan and produced:
- research.md: chose @xyflow/react (React Flow v12) + @dagrejs/dagre; confirmed backend is complete; no backend changes needed
- data-model.md: documented existing AgentRun/AgentRunStep models + frontend-only GraphNode/GraphEdge types + node visual mapping
- plan.md: full implementation plan across 6 phases (A–F), 20 tasks covering graph transformer, ellipse nodes, runs list panel, node detail popup, page assembly, and edge cases

Key architectural decisions:
- @xyflow/react for graph rendering (ellipse via border-radius: 9999px on custom nodes)
- @dagrejs/dagre for auto-layout (ranksep=120, nodesep=160)
- No backend changes required
- New route: frontend/src/app/(dashboard)/runs/page.tsx

## Outcome

- ✅ Impact: Plan is ready; /sp.tasks can now generate testable atomic tasks
- 🧪 Tests: Planned in tasks phase — graph-transformer.test.ts, runs-list-panel.test.tsx, graph-canvas.test.tsx
- 📁 Files: research.md, data-model.md, plan.md created under specs/1-agent-runs-graph/
- 🔁 Next prompts: /sp.tasks to generate atomic tasks; then implement Phase A (graph transformer)
- 🧠 Reflection: Backend was already complete — entire feature is frontend-only. Dagre layout cleanly solves the spacing and parallel node placement requirements.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): none yet
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): run /sp.tasks and verify tasks map to the 6 phases in plan.md
