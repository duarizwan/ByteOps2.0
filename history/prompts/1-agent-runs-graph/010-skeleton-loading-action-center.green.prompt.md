---
id: "010"
title: Skeleton Loading for Action Center
stage: green
date: 2026-05-31
surface: agent
model: claude-sonnet-4-6
feature: 1-agent-runs-graph
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.phr
labels: ["skeleton", "loading-state", "action-center", "animate-pulse", "ux"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/runs/action-center.tsx
tests:
  - npx tsc --noEmit (no errors in source files)
---

## Prompt

You are implementing Task 5: Skeleton Loading for Action Center.

## Task Description

**File:** `frontend/src/components/runs/action-center.tsx` at `D:\OneDrive - Jonas Software\Dua Stuff\uni\Byteops\ByteOps-master`

**Step 1: Add ActionCardSkeleton component before the ActionCenter export**

Before the `export function ActionCenter()` declaration, add this component function:

```tsx
function ActionCardSkeleton() {
    return (
        <div style={{
            display: "flex",
            borderRadius: 8,
            overflow: "hidden",
            border: "1px solid var(--border)",
            background: "var(--card)",
            opacity: 0.6,
        }}>
            {/* Status bar placeholder */}
            <div style={{ width: 3, flexShrink: 0, background: "var(--accent)" }} />
            {/* Body */}
            <div style={{ flex: 1, padding: "10px 12px", display: "flex", gap: 10, alignItems: "flex-start" }}
                 className="animate-pulse">
                {/* Platform badge placeholder */}
                <div style={{ width: 44, height: 18, borderRadius: 5, background: "var(--accent)", flexShrink: 0, marginTop: 1 }} />
                {/* Text placeholder */}
                <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: 6 }}>
                    <div style={{ height: 10, borderRadius: 4, background: "var(--accent)", width: "60%" }} />
                    <div style={{ height: 10, borderRadius: 4, background: "var(--accent)", width: "80%" }} />
                    <div style={{ height: 9,  borderRadius: 4, background: "var(--accent)", width: "40%" }} />
                </div>
                {/* Right column placeholder */}
                <div style={{ width: 36, display: "flex", flexDirection: "column", gap: 6, alignItems: "flex-end" }}>
                    <div style={{ width: 18, height: 18, borderRadius: 4, background: "var(--accent)" }} />
                    <div style={{ width: 24, height: 8,  borderRadius: 4, background: "var(--accent)" }} />
                    <div style={{ width: 36, height: 18, borderRadius: 5, background: "var(--accent)" }} />
                </div>
            </div>
        </div>
    );
}
```

**Step 2: Show skeletons when isLoading**

In the `ActionCenter` component, inside the "Feed" div (the `<div style={{ flex: 1, overflowY: "auto", ... }}>` that contains all the section content), add the loading skeleton guard at the VERY BEGINNING, before the `{/* Awaiting Approval */}` comment. The skeletons should show only when `isLoading` is true:

```tsx
{/* Skeleton loading state */}
{isLoading && (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        <ActionCardSkeleton />
        <ActionCardSkeleton />
        <ActionCardSkeleton />
    </div>
)}
```

Insert this block just before the `{/* Awaiting Approval */}` section.

**Step 3: TypeScript check**
```bash
cd frontend && npx tsc --noEmit
```

**Step 4: Commit**
```bash
git add frontend/src/components/runs/action-center.tsx
git commit -m "feat: add skeleton loading state to Action Center"
```

## Context

**Tech stack:** Next.js 15, React 19, TypeScript, Tailwind CSS v4. No shadcn/ui — all custom inline styles.

**The file is ~287 lines.** Key structure:
- `useAgentRuns()` hook returns `{ runs, isLoading }` — `isLoading` starts as `true`, goes `false` after first fetch
- The component already uses `isLoading` in one conditional (`dateGroups.length === 0 && !isLoading` prevents the empty state from showing while loading)
- The skeleton should appear WHILE `isLoading` is true, alongside (or instead of) the empty sections

**Existing skeleton pattern** (from `context-panel.tsx` in the same project):
- `animate-pulse` Tailwind class on the container
- `bg-accent` / `var(--accent)` color for placeholder blocks
- Rounded divs mimicking card structure

The `ActionCardSkeleton` you're adding follows this same pattern, with dimensions matching the real `ActionCard` layout (3px status bar, platform badge, text lines, right column).

**The skeleton shows in addition to actual content while loading is true** — this is intentional. In practice, the first load shows skeletons for ~200ms before real data arrives. Don't suppress real content sections when isLoading is true; just prepend the skeleton group.

Work from: `D:\OneDrive - Jonas Software\Dua Stuff\uni\Byteops\ByteOps-master`

## Response snapshot

Added `ActionCardSkeleton` private component before `ActionCenter` export, mimicking real `ActionCard` layout (3px status bar, platform badge, 3 text lines, right column) with `animate-pulse` and `var(--accent)` placeholders. Inserted a 3-skeleton group inside the Feed div, guarded by `{isLoading && ...}`, immediately before the Awaiting Approval section. TypeScript check showed zero errors in source files (pre-existing test-file errors for missing `@types/jest` are unrelated). Committed as `feat: add skeleton loading state to Action Center` (commit d50113f).

## Outcome

- Impact: Action Center now displays 3 animated placeholder cards during the ~200ms initial data fetch, eliminating layout shift and blank-panel flash on first load.
- Tests: `npx tsc --noEmit` — no errors in source files; pre-existing test-runner type errors in `tests/` are unrelated to this change.
- Files: `frontend/src/components/runs/action-center.tsx` (+40 lines)
- Next prompts: Task 6 — Skeleton loading for trace drawer (graph-canvas.tsx, trace-drawer.tsx)
- Reflection: Placing the skeleton guard at the very top of the Feed div (before all conditional sections) is the correct pattern — it shows immediately on mount without interfering with any real-content rendering logic.

## Evaluation notes (flywheel)

- Failure modes observed: None. Task instructions were precise and unambiguous; all placeholders filled without guessing.
- Graders run and results (PASS/FAIL): tsc --noEmit PASS (source files clean)
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Consider adding a `skeletonCount` prop to `ActionCardSkeleton` caller so count can be data-driven (e.g., match last known run count from localStorage).
