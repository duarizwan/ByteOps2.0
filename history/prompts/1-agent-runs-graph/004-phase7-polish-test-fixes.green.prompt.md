---
id: "004"
title: Phase 7 Polish and Test Fixes
stage: green
date: 2026-05-30
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: dua.rizwan@jonasclub.com
command: start implementing
labels: ["green","phase7","polish","test-fixes","css-vars","tdd"]
links:
  spec: specs/1-agent-runs-graph/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/runs/graph-nodes/ellipse-node.tsx (labelColor #f87171, font-mono class, color-mix + var(--card) background)
  - frontend/src/components/runs/graph-canvas.tsx (var(--background), smoothstep edges, #334155 stroke)
  - frontend/src/components/runs/node-detail-popup.tsx (var(--popover) background, durationMs display)
  - frontend/src/components/runs/runs-list-panel.tsx (var(--card) background)
  - frontend/src/lib/graph-transformer.ts (step.name used as label — raw monospace identifier, not humanized)
  - frontend/tests/agent-activity.test.tsx (describe.skip — Activity tab removed PHR-036)
  - specs/1-agent-runs-graph/tasks.md (T025–T029 marked complete)
tests:
  - frontend/tests/ellipse-node.test.tsx (all pass)
  - frontend/tests/graph-canvas.test.tsx (all pass)
  - frontend/tests/node-detail-popup.test.tsx (all pass)
  - frontend/tests/runs-list-panel.test.tsx (all pass)
  - frontend/tests/graph-transformer.test.ts (all pass)
---

## Prompt

start implementing

(context: referring to the 1-agent-runs-graph Phase 7 Polish tasks T025–T029)

## Response snapshot

Discovered Phase 7 (T025–T029) was already implemented in code during the main sprint but tasks.md was not updated. Found 14 pre-existing test failures and fixed them all:

**Component fixes (6 surgical edits):**
- `ellipse-node.tsx`: failed color `#FCA5A5` → `#f87171`; added `className="font-mono"` to label span; background changed to `color-mix(in srgb, ${typeColor} 12%, var(--card))`
- `graph-canvas.tsx`: canvas background `transparent` → `var(--background)`; edges `type: "default"` → `type: "smoothstep"`; stroke `#475569` → `#334155`
- `node-detail-popup.tsx`: background `#06101E` → `var(--popover)`; added `durationMs` pill to status section
- `runs-list-panel.tsx`: background `#080F1E` → `var(--card)`
- `graph-transformer.ts`: label `humanizeStepName(step.name)` → `step.name` (raw monospace format per FR-009)

**Test cleanup:**
- `agent-activity.test.tsx`: Activity tab tests → `describe.skip` (Activity tab intentionally removed PHR-036)

**Result**: 108/108 passing, 3 skipped (stale Activity tab tests), 0 failures.

## Outcome

- ✅ Impact: All 29 tasks complete; all Phase 7 polish implemented; test suite fully green
- 🧪 Tests: 108 pass, 3 skip (stale), 0 fail — up from 97 pass / 14 fail
- 📁 Files: 7 files modified
- 🔁 Next prompts: /verify to confirm graph renders correctly in browser, then /sp.git.commit_pr to ship
- 🧠 Reflection: Source-level tests (readFileSync checks) are brittle to implementation choices — humanizeStepName was a sensible UI choice but conflicted with the spec's monospace-identifier requirement. The spec wins.

## Evaluation notes (flywheel)

- Failure modes observed: 14 test failures were pre-existing from the main sprint — implementation used hardcoded dark-theme hex colors instead of CSS vars, and humanized labels instead of raw step names
- Graders run and results (PASS/FAIL): 108/108 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): verify /runs page in browser — confirm color-mix backgrounds render correctly with both light and dark themes
