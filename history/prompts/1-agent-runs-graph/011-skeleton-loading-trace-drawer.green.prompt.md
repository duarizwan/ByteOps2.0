---
id: "011"
title: Skeleton Loading for Trace Drawer
stage: green
date: 2026-05-31
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.phr
labels: ["skeleton-loading", "trace-drawer", "graph-canvas", "ux", "spinner", "useEffect", "onLoad"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/runs/graph-canvas.tsx
  - frontend/src/components/runs/trace-drawer.tsx
tests:
  - npx tsc --noEmit (no new errors in modified source files)
---

## Prompt

--title "Skeleton loading for trace drawer" --stage green --feature agent-runs-graph

## Response snapshot

Implemented Task 6: added an `onLoad?: () => void` prop to `GraphCanvasProps` (threading it through both the exported `GraphCanvas` wrapper and `GraphCanvasInner`), wired a `useEffect` inside `GraphCanvasInner` to fire `onLoad` when `isLoading` transitions to false. In `trace-drawer.tsx`, added `useState`/`useEffect` imports, a `isGraphReady` state that resets to `false` on each new `run?.id`, and a positioned spinner overlay that hides once `onLoad` fires. TypeScript check passed with zero new errors (all existing errors are pre-existing missing `@types/jest` in test files). Changes committed as `bcbbac7`.

## Outcome

- Impact: The trace drawer now shows a centered CSS spinner overlay ("Loading trace…") each time a new run is opened, disappearing once ReactFlow finishes fetching and rendering. The per-run reset pattern (`useEffect` on `run?.id`) ensures the loader reappears for every distinct trace selection.
- Tests: TypeScript noEmit — no new errors in `graph-canvas.tsx` or `trace-drawer.tsx`. All pre-existing test errors are unrelated (missing `@types/jest`).
- Files: `frontend/src/components/runs/graph-canvas.tsx`, `frontend/src/components/runs/trace-drawer.tsx`
- Next prompts: Mark Task 6 complete; confirm all 6 Action Center tasks are done; optionally verify spinner visually in running app.
- Reflection: The two-component prop-threading pattern (`GraphCanvas` wrapper → `GraphCanvasInner`) required updating both the interface and both function signatures — easy to miss the outer wrapper when only reading the inner component.

## Evaluation notes (flywheel)

- Failure modes observed: None. The `onLoad` callback correctly fires after `isLoading` goes false with either `run` or `error` present, covering both success and error fetch outcomes. The `isGraphReady` reset effect correctly uses `run?.id` so it fires on null→run transitions as well.
- Graders run and results (PASS/FAIL): TypeScript noEmit PASS (no new errors in modified files).
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add a fade-out CSS transition on the spinner overlay for a smoother UX when the graph appears.
