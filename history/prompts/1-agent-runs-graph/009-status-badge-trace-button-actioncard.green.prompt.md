---
id: "009"
title: Status Badge and Trace Button ActionCard
stage: green
date: 2026-05-31
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.phr
labels: ["status-badge", "trace-button", "action-card", "ui", "inline-styles", "react"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/runs/action-card.tsx
tests:
  - none
---

## Prompt

Task 4: Status Badge and Trace Button on ActionCard.

**File:** `frontend/src/components/runs/action-card.tsx`

**Step 1: Add STATUS_BADGE map after the existing BADGE constant**

The file currently has a `BADGE` constant (lines 6–13) and a `STATUS_BAR` constant (lines 15–18). After line 18 (end of STATUS_BAR), add:

```typescript
const STATUS_BADGE: Record<string, { label: string; bg: string; text: string }> = {
    completed:        { label: "Completed",       bg: "rgba(34,197,94,.15)",   text: "#22C55E" },
    waiting_approval: { label: "Pending Approval", bg: "rgba(234,179,8,.15)",  text: "#EAB308" },
    failed:           { label: "Failed",           bg: "rgba(239,68,68,.15)",  text: "#F87171" },
    planning:         { label: "In Progress",      bg: "rgba(59,130,246,.12)", text: "#60A5FA" },
    running:          { label: "In Progress",      bg: "rgba(59,130,246,.12)", text: "#60A5FA" },
    cancelled:        { label: "Cancelled",        bg: "rgba(148,163,184,.1)", text: "#94A3B8" },
};
```

**Step 2: Compute `statusBadge` inside the ActionCard component**

In the `ActionCard` function body, after the existing line that destructures `{ summary, detail }` (line 39), add:

```typescript
const statusBadge = STATUS_BADGE[run.status] ?? { label: run.status, bg: "rgba(148,163,184,.1)", text: "#94A3B8" };
```

**Step 3: Render the status badge pill before the summary text**

Find the `{/* Text */}` div block (lines 75–83). Replace with a version that includes a badge pill above the summary text, using a flex wrapper div with the span styled at fontSize 10, fontWeight 600, padding "1px 6px", borderRadius 4.

**Step 4: Make the trace button visually prominent**

Replace the plain `trace →` text button with a pill button: blue-tinted background `rgba(59,130,246,.08)`, border `1px solid rgba(59,130,246,.25)`, borderRadius 5, padding "3px 8px", with onMouseEnter/onMouseLeave hover handlers that deepen the tint and border opacity. aria-label changed to "View trace", text changed to "Trace →".

**Step 5: TypeScript check**
```bash
cd frontend && npx tsc --noEmit
```

**Step 6: Commit**
```bash
git add frontend/src/components/runs/action-card.tsx
git commit -m "feat: add status badge and prominent trace button to ActionCard"
```

**Tech stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v4. No shadcn/ui — all custom inline styles.

**AgentRun.status values**: `"planning" | "waiting_approval" | "running" | "completed" | "failed" | "cancelled"`

## Response snapshot

Applied all four steps to `action-card.tsx`: added the `STATUS_BADGE` constant (6 status entries with label/bg/text), computed `statusBadge` with fallback inside `ActionCard`, rendered a status pill span above the summary text, and replaced the bare `trace →` button with a bordered blue-tinted pill button with hover state handlers. TypeScript check showed zero errors in `action-card.tsx` (pre-existing test-file errors for missing `@types/jest` were unrelated). Committed as `feat: add status badge and prominent trace button to ActionCard`.

## Outcome

- ✅ Impact: ActionCard now surfaces a coloured status pill (Completed/Pending Approval/Failed/In Progress/Cancelled) above the summary text, and the Trace button is visually distinct as a bordered blue pill with hover feedback — making run state instantly readable and the trace action easier to discover.
- 🧪 Tests: TypeScript noEmit check passed for action-card.tsx; no unit tests added (component is purely presentational).
- 📁 Files: frontend/src/components/runs/action-card.tsx (167 lines, +55 net)
- 🔁 Next prompts: Task 5 — Skeleton loading for Action Center (action-center.tsx); Task 6 — Skeleton loading for trace drawer (graph-canvas.tsx, trace-drawer.tsx).
- 🧠 Reflection: All four steps were mechanical and sequentially independent — reading the file first before any edits ensured each `old_string` matched exactly, with no merge conflicts.

## Evaluation notes (flywheel)

- Failure modes observed: None. All four edits landed cleanly on first attempt; `old_string` uniqueness was straightforward given the small file size.
- Graders run and results (PASS/FAIL): `npx tsc --noEmit` — PASS (zero errors in action-card.tsx).
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Add a Vitest/Testing Library snapshot test for ActionCard that asserts the status pill text and trace button label render correctly for each status value.
