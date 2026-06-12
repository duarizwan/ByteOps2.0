# Research: Action Center Redesign

**Branch**: `1-agent-runs-graph` | **Date**: 2026-05-31  
**Supersedes**: prior research.md (Agent Runs Graph Page — graph library decisions remain valid and referenced below)

---

## Decision 1 — Approve / Cancel Endpoints (Backend)

**Decision**: Both endpoints already exist. No backend work required for approve/cancel.

**Evidence** (`backend/app/api/agent_runs.py`):
- `POST /api/agent-runs/{run_id}/approve` — line 67: validates `WAITING_APPROVAL` status, calls `resolve_approval(str(run_id), approved=True)`, returns `{"status": "approved", "run_id": str(run_id)}`.
- `POST /api/agent-runs/{run_id}/cancel` — line 155: validates `WAITING_APPROVAL` status, calls `resolve_approval(str(run_id), approved=False)`, sets `run.status = CANCELLED`, returns `{"status": "cancelled", "run_id": str(run_id)}`.

**Alternatives considered**:
- Implementing endpoints from scratch — not needed; they're already complete and auth-gated.

---

## Decision 2 — Retry Endpoint

**Decision**: Not implemented in this phase. Stretch goal per spec.

**Rationale**: The spec explicitly marks `POST /api/agent-runs/{id}/retry` as stretch. No existing endpoint exists. Deferring avoids scope creep on the frontend redesign.

---

## Decision 3 — `summarizeAction` — Finding the First CRUD Tool Call

**Decision**: Traverse `run.steps` in order; return the first step where `step_type === "tool_call"` AND `WRITE_VERBS.has(step.name.split("_")[0])`. Extract summary and detail from `step.input`.

**Rationale**: Mirrors the existing `hasCrudOperation` filter (already in `runs-page.tsx:17-23`) — consistent logic, easily testable as a pure function.

**Fallback**: If no matching step is found, fall back to `intent` from `run.intent` as the summary and `run.steps[0]?.name` humanized as detail.

---

## Decision 4 — TraceDrawer Reuse

**Decision**: `TraceDrawer` wraps the existing `<GraphCanvas selectedRunId={runId} />` component unchanged. The drawer is a CSS `transform: translateX()` slide-in with a fixed-position overlay.

**Rationale**: Spec explicitly states GraphCanvas is unchanged. Using the same inline-style approach already used throughout `runs-page.tsx` keeps the codebase consistent without adding a Radix/shadcn dependency for a single drawer.

**Alternatives considered**:
- Radix Sheet component — adds dependency; inconsistent with existing inline-style pattern in the runs components.

---

## Decision 5 — Filter Tab State

**Decision**: `filterTab: "all" | "pending" | "failed"` stored in React component state inside `ActionCenter`. No URL query parameter.

**Rationale**: Filter state is ephemeral UI preference, not a shareable URL. Consistent with how the existing runs page manages `selectedRunId` in state.

---

## Decision 6 — ActionCard Layout Approach

**Decision**: Inline styles (consistent with `runs-page.tsx`) for the card layout. No new Tailwind classes.

**Rationale**: The existing `runs-page.tsx` uses inline styles throughout. Mixing Tailwind and inline styles inconsistently would create maintenance debt. Pure inline-style approach keeps the new components visually consistent with the page shell.

---

## Decision 7 — `hasCrudOperation` Filter

**Decision**: Unchanged — Action Center still uses the existing `hasCrudOperation` function from `runs-page.tsx`.

**Rationale**: Spec explicitly states this filter is unchanged.

---

## Decision 8 — Graph Library (Carried Forward)

The `@xyflow/react` + `@dagrejs/dagre` decisions from the original research.md remain valid. `GraphCanvas` and `graph-transformer.ts` are reused as-is inside the `TraceDrawer`.

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|-----------|
| Are approve/cancel endpoints implemented? | YES — both exist in `agent_runs.py` |
| Does retry endpoint exist? | NO — stretch goal, deferred |
| How does `summarizeAction` find the CRUD step? | First `tool_call` step where name verb is in WRITE_VERBS |
| How to implement TraceDrawer? | CSS transform slide-in wrapping existing GraphCanvas |
| Filter tabs — URL or state? | React component state only |
| New packages needed? | None — all existing dependencies sufficient |
| Backend changes needed? | None for Phase 1 |
