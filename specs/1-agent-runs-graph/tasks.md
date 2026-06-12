# Tasks: Action Center Redesign

**Input**: `specs/1-agent-runs-graph/plan.md`, `docs/superpowers/specs/2026-05-31-action-center-design.md`  
**Branch**: `1-agent-runs-graph` | **Date**: 2026-05-31  
**TDD**: Mandatory (Constitution §IV) — RED → GREEN → REFACTOR enforced throughout

**User Stories**:
- **US1 (P1)**: Plain-English action feed — user understands what AI did in < 5 s, no graph required
- **US2 (P1)**: Pending approvals surfaced prominently with inline Approve / Cancel
- **US3 (P2)**: Failed actions grouped with human-readable errors and fix CTAs
- **US4 (P2)**: Graph accessible on demand via "trace →" slide-in drawer
- **US5 (P2)**: Filter tabs (All / Pending / Failed) narrow the feed

---

## Phase 1: Setup

**Purpose**: Confirm no new packages needed (verified in research.md), create stub files so TypeScript imports resolve during TDD.

- [x] T001 Verify `@xyflow/react` and `@dagrejs/dagre` are present in `frontend/package.json` (already installed — confirm only, do not reinstall)
- [x] T002 [P] Create empty stub `frontend/src/lib/summarize-action.ts` (placeholder export so imports don't break during TDD)
- [x] T003 [P] Create empty stub `frontend/src/lib/classify-error.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pure-logic utilities used by every card component. MUST be complete before any user story phase.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Types

- [x] T004 Define shared TypeScript types in `frontend/src/lib/action-center-types.ts`: `ActionSummary`, `ActionErrorCategory` (`"auth" | "timeout" | "unknown"`), `FilterTab` (`"all" | "pending" | "failed"`), `CategorizedRuns`

### summarizeAction — TDD (RED first)

- [x] T005 Write unit tests for `summarizeAction` in `frontend/src/lib/summarize-action.test.ts` covering:
  - All 16 intent × tool combinations from data-model.md lookup table (gmail/send_email, gmail/reply_to_email, gmail/trash_email, gmail/create_draft, calendar/create_event, calendar/update_event, calendar/delete_event, slack/send_message, jira/create_issue, jira/update_issue, jira/add_comment, github/merge_pull_request, github/create_issue, dropbox/upload_file, dropbox/delete_file, dropbox/move_file)
  - Missing `step.input` fields → fallback strings, no crash
  - No matching CRUD step found → `"{intent} action completed"` fallback
  - Confirm tests FAIL before T006

- [x] T006 Implement `summarizeAction(run: AgentRun): ActionSummary` in `frontend/src/lib/summarize-action.ts` (GREEN — make T005 pass)

### classifyError — TDD (RED first)

- [x] T007 Write unit tests for `classifyError` in `frontend/src/lib/classify-error.test.ts`:
  - "401" → `"auth"`, "403" → `"auth"`, "token" → `"auth"`, "expired" → `"auth"`, "unauthorized" → `"auth"`
  - "timeout" → `"timeout"`, "503" → `"timeout"`, "api error" → `"timeout"`
  - `null` → `"unknown"`, unrecognised string → `"unknown"`
  - Confirm tests FAIL before T008

- [x] T008 Implement `classifyError(error: string | null): ActionErrorCategory` in `frontend/src/lib/classify-error.ts` (GREEN — make T007 pass)

**Checkpoint**: `npm run test -- summarize-action` and `npm run test -- classify-error` both PASS before moving to Phase 3

---

## Phase 3: US1 — Plain-English Action Feed (Priority: P1) 🎯 MVP

**Goal**: User sees completed/cancelled runs as readable plain-English cards in a date-grouped feed.

**Independent Test**: Navigate to `/runs` with at least one completed gmail run — see a card reading "Sent email to …" with a subject detail line. No graph visible by default.

### Tests (RED first)

- [x] T009 [US1] Write failing tests for `ActionCard` in `frontend/src/components/runs/action-card.test.tsx`:
  - Renders green status bar for completed, grey for cancelled
  - Renders platform badge with correct label for all six platforms
  - Renders `summary` and `detail` strings from `summarizeAction` output
  - Renders relative timestamp
  - "trace →" button fires `onTrace(run.id)` callback
  - Confirm tests FAIL before T010

### Implementation (GREEN)

- [x] T010 [US1] Implement `ActionCard` in `frontend/src/components/runs/action-card.tsx` (make T009 pass):
  - 3px status bar left border (green = `var(--chart-2)` for completed, `var(--muted-foreground)` for cancelled)
  - Platform badge: coloured pill using brand constants from data-model.md
  - Summary line (bold), detail line (muted), relative timestamp
  - "trace →" button fires `onTrace(run.id)`

- [x] T011 [P] [US1] Implement `ActionCenterTopBar` section inline in `frontend/src/components/runs/action-center.tsx`:
  - `← Dashboard` button (navigates to `/dashboard`)
  - "Action Center" title with Activity icon
  - Placeholder for FilterTabs (wired in Phase 7)

- [x] T012 [US1] Implement `ActionFeed` with date grouping inline in `frontend/src/components/runs/action-center.tsx`:
  - `groupByDate(runs)` helper: groups by ISO date (YYYY-MM-DD), labels "Today" / "Yesterday" / formatted date
  - Renders `DateSeparator` label + `ActionCard` per run
  - Empty state: "No agent runs yet. Send a message in chat to see your AI's actions here."

- [x] T013 [US1] Implement `ActionCenter` top-level shell in `frontend/src/components/runs/action-center.tsx`:
  - Uses `useAgentRuns()` hook
  - Applies existing `hasCrudOperation` filter (copy from `runs-page.tsx:17-23`, do not modify original)
  - State: `filterTab: FilterTab`, `traceRunId: string | null`, `dismissedIds: Set<string>`
  - Categorizes runs into `pending` / `failed` / `history` via `categorize()` function
  - Renders only `ActionFeed` for now (approval/failed sections wired in Phases 4–5)

- [x] T014 [US1] Update `frontend/src/app/(dashboard)/runs/page.tsx` — replace `<RunsPage />` import with `<ActionCenter />`

- [x] T015 [US1] Update sidebar nav label from "Runs" / "Agent Runs" to "Action Center" in `frontend/src/components/dashboard/collapsible-sidebar.tsx`

**Checkpoint**: `/runs` renders Action Center feed. Completed runs appear as readable cards. Graph gone from default view. `npm run test -- action-card` passes.

---

## Phase 4: US2 — Pending Approvals (Priority: P1)

**Goal**: Runs with `waiting_approval` status appear as amber cards pinned above the feed with Approve / Cancel / Edit in chat buttons.

**Independent Test**: With a `waiting_approval` run present — amber card is visible at page top. Click Approve → card disappears. Click Cancel → card disappears.

### Tests (RED first)

- [x] T016 [US2] Write failing tests for `AwaitingApprovalCard` in `frontend/src/components/runs/awaiting-approval-card.test.tsx`:
  - Renders amber 3px left border
  - Renders platform badge
  - "what it's about to do" summary line rendered (from `summarizeAction`)
  - "Approve" button present; fires `onApprove(run.id)` callback
  - "Cancel" button present; fires `onCancel(run.id)` callback
  - "Edit in chat →" renders as link to `/dashboard`
  - Approve button shows loading state while in-flight
  - 409 response on approve → treated as stale, fires `onApprove` to dismiss
  - Confirm tests FAIL before T017

### Implementation (GREEN)

- [x] T017 [US2] Implement `AwaitingApprovalCard` in `frontend/src/components/runs/awaiting-approval-card.tsx` (make T016 pass):
  - Approve: `api(`/api/agent-runs/${run.id}/approve`, { method: "POST" })` → call `onApproved(run.id)`
  - Cancel: `api(`/api/agent-runs/${run.id}/cancel`, { method: "POST" })` → call `onCancelled(run.id)`
  - On error (non-409): show inline error text, restore card
  - Optimistic: parent dismisses card immediately on user action (wired in T018)

- [x] T018 [US2] Add `AwaitingApprovalSection` to `ActionCenter` in `frontend/src/components/runs/action-center.tsx`:
  - Renders only when `pending.length > 0`
  - Section header: "Awaiting Approval" (amber text)
  - Renders `AwaitingApprovalCard` per pending run
  - `onApproved` / `onCancelled` add run ID to `dismissedIds` (optimistic)

**Checkpoint**: Amber approval cards appear at top. Approve/Cancel work and card disappears instantly. `npm run test -- awaiting-approval-card` passes.

---

## Phase 5: US3 — Failed Actions with Fix CTAs (Priority: P2)

**Goal**: Failed runs appear as red cards with a human-readable error and a context-appropriate fix CTA.

**Independent Test**: With a failed run where `run.error` contains "401" — red card shows a "Reconnect Gmail →" link to `/settings`.

### Tests (RED first)

- [x] T019 [US3] Write failing tests for `NeedsFixingCard` in `frontend/src/components/runs/needs-fixing-card.test.tsx`:
  - Renders red 3px left border (`var(--destructive)`)
  - Renders platform badge
  - Renders `summarizeAction` summary as the "what failed" line
  - Renders `run.error` text (truncated to 120 chars)
  - Auth error (`classifyError` → "auth") → renders `<a href="/settings">Reconnect {platform} →</a>`
  - Timeout error → renders disabled "Retry →" button
  - Unknown error → no CTA rendered
  - Confirm tests FAIL before T020

### Implementation (GREEN)

- [x] T020 [US3] Implement `NeedsFixingCard` in `frontend/src/components/runs/needs-fixing-card.tsx` (make T019 pass)

- [x] T021 [US3] Add `NeedsFixingSection` to `ActionCenter` in `frontend/src/components/runs/action-center.tsx`:
  - Renders only when `failed.length > 0`
  - Section header: "Needs Fixing" (red text)
  - Renders `NeedsFixingCard` per failed run

**Checkpoint**: Red failed cards appear below amber section. Auth error → settings link renders. `npm run test -- needs-fixing-card` passes.

---

## Phase 6: US4 — Trace Drawer (Priority: P2)

**Goal**: "trace →" on any ActionCard opens a 400 px slide-in drawer containing the unchanged `GraphCanvas`.

**Independent Test**: Click "trace →" on a completed card → drawer slides in from right showing the execution graph. Click × or click backdrop → drawer closes.

### Tests (RED first)

- [x] T022 [US4] Write failing tests for `TraceDrawer` in `frontend/src/components/runs/trace-drawer.test.tsx`:
  - Does not render visible content when `runId` is null
  - Renders when `runId` is provided
  - Header shows run summary text
  - × close button fires `onClose` callback
  - Backdrop overlay fires `onClose` on click
  - Confirm tests FAIL before T023

### Implementation (GREEN)

- [x] T023 [US4] Implement `TraceDrawer` in `frontend/src/components/runs/trace-drawer.tsx` (make T022 pass):
  - `position: fixed; right: 0; top: 0; bottom: 0; width: 400px`
  - `transform: translateX(runId ? "0" : "100%"); transition: transform 0.25s ease; z-index: 50`
  - Header: run summary (from `summarizeAction`) + × close button
  - Body: `<GraphCanvas selectedRunId={runId} />` (unchanged, no modifications)
  - Backdrop: `position: fixed; inset: 0; background: rgba(0,0,0,0.4); z-index: 49` — click fires `onClose`

- [x] T024 [US4] Wire `TraceDrawer` into `ActionCenter` in `frontend/src/components/runs/action-center.tsx`:
  - Pass `traceRunId` and `onClose={() => setTraceRunId(null)}` to `TraceDrawer`
  - Pass `onTrace={(id) => setTraceRunId(id)}` down to `ActionCard` components

**Checkpoint**: "trace →" opens drawer with graph. Close works. `npm run test -- trace-drawer` passes.

---

## Phase 7: US5 — Filter Tabs (Priority: P2)

**Goal**: Three tabs — All / Pending / Failed — narrow the visible sections of the Action Center.

**Independent Test**: Click "Pending" → only AwaitingApproval section visible, feed hidden. Click "Failed" → only NeedsFixing section. Click "All" → all sections visible.

### Tests (RED first)

- [x] T025 [US5] Write failing tests for `FilterTabs` in `frontend/src/components/runs/filter-tabs.test.tsx`:
  - Renders three tab buttons: "All", "Pending", "Failed"
  - Active tab visually distinguished (aria-selected)
  - Clicking each tab fires `onTabChange` with correct `FilterTab` value
  - Confirm tests FAIL before T026

### Implementation (GREEN)

- [x] T026 [US5] Implement `FilterTabs` in `frontend/src/components/runs/filter-tabs.tsx` (make T025 pass)

- [x] T027 [US5] Wire `FilterTabs` into `ActionCenterTopBar` and `ActionCenter` state in `frontend/src/components/runs/action-center.tsx`:
  - `filterTab === "pending"` → show only `AwaitingApprovalSection`, hide feed
  - `filterTab === "failed"` → show only `NeedsFixingSection`, hide pending
  - `filterTab === "all"` → show all three sections (default)
  - Implement `categorize(runs, filterTab, dismissedIds): CategorizedRuns` function

**Checkpoint**: Filter tabs correctly narrow the view. `npm run test -- filter-tabs` passes.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T028 [P] Add empty state for `AwaitingApprovalSection` when `filterTab === "pending"` and `pending.length === 0`: "No pending approvals right now." — `frontend/src/components/runs/action-center.tsx`
- [x] T029 [P] Add empty state for `NeedsFixingSection` when `filterTab === "failed"` and `failed.length === 0`: "No failed actions." — `frontend/src/components/runs/action-center.tsx`
- [x] T030 Update page `<title>` metadata to "Action Center — ByteOps" in `frontend/src/app/(dashboard)/runs/page.tsx`
- [x] T031 Add deprecation comment to `frontend/src/components/runs/runs-page.tsx`: `// Deprecated: superseded by ActionCenter — safe to delete after QA sign-off` (do NOT delete the file yet)
- [x] T032 [P] Run full test suite `npm run test` — confirm all new tests pass, zero regressions — 179 passed, 0 failed
- [ ] T033 [P] Manual smoke test per `specs/1-agent-runs-graph/quickstart.md` — verify all five user stories end-to-end

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)
    └─► Phase 2 (Foundational) ◄─ BLOCKS ALL STORIES
            └─► Phase 3 (US1 — Feed + Shell) 🎯 MVP
                    ├─► Phase 4 (US2 — Approvals) ← needs ActionCenter shell
                    ├─► Phase 5 (US3 — Failed)    ← needs ActionCenter shell, parallel with Phase 4
                    ├─► Phase 6 (US4 — Drawer)    ← needs ActionCard's onTrace prop
                    └─► Phase 7 (US5 — Filters)   ← needs all sections present
                                └─► Phase 8 (Polish)
```

### User Story Independence

| Story | Depends On | Can Parallelise With |
|-------|-----------|---------------------|
| US1 (Feed) | Phase 2 complete | — |
| US2 (Approvals) | US1 ActionCenter shell (T013) | US3 |
| US3 (Failed) | US1 ActionCenter shell (T013) | US2 |
| US4 (Drawer) | US1 ActionCard with `onTrace` prop (T010) | US2, US3 |
| US5 (Filters) | All sections from US1–US3 present | — |

### Parallel Opportunities

- T002 + T003 (stub files): fully parallel [P]
- T005 + T007 (test files for summarizeAction + classifyError): fully parallel [P]
- T009 card test, T011 top bar, T012 feed: T011 is parallel to T009 [P]
- T016 + T019 + T022 + T025 (all card test files once Phase 3 done): fully parallel [P]
- T017 + T020 + T023 + T026 (card implementations): fully parallel once their tests are RED [P]
- T028 + T029 + T032 + T033 (polish): fully parallel [P]

---

## Parallel Execution Example: Foundational Phase

```bash
# After T004 (types) — run in parallel:
Task T005: "Write summarizeAction tests" → frontend/src/lib/summarize-action.test.ts
Task T007: "Write classifyError tests"   → frontend/src/lib/classify-error.test.ts

# After T005 RED confirmed:
Task T006: "Implement summarizeAction"   → frontend/src/lib/summarize-action.ts

# After T007 RED confirmed:
Task T008: "Implement classifyError"     → frontend/src/lib/classify-error.ts
```

## Parallel Execution Example: Card Phases (after Phase 3 complete)

```bash
# All card tests can be written at the same time:
Task T016: "AwaitingApprovalCard tests"
Task T019: "NeedsFixingCard tests"
Task T022: "TraceDrawer tests"
Task T025: "FilterTabs tests"
```

---

## Implementation Strategy

### MVP (US1 + US2 — Phases 1–4)

1. Phases 1–2: Setup + Foundational utilities
2. Phase 3: Action Feed — readable cards, page shell, nav label update
3. Phase 4: Pending Approvals — approve/cancel inline
4. **STOP and VALIDATE**: Users see the plain-English feed AND can approve/cancel
5. Meets both P1 success criteria from the spec

### Full Delivery

1. MVP (above)
2. Phase 5: Failed Actions with fix CTAs
3. Phase 6: TraceDrawer — graph on demand
4. Phase 7: Filter Tabs
5. Phase 8: Polish

---

## Task Count Summary

| Phase | Tasks | Notes |
|-------|-------|-------|
| Phase 1: Setup | 3 | T001–T003 |
| Phase 2: Foundational | 5 | T004–T008 (TDD) |
| Phase 3: US1 Feed | 7 | T009–T015 (TDD) |
| Phase 4: US2 Approvals | 3 | T016–T018 (TDD) |
| Phase 5: US3 Failed | 3 | T019–T021 (TDD) |
| Phase 6: US4 Drawer | 3 | T022–T024 (TDD) |
| Phase 7: US5 Filters | 3 | T025–T027 (TDD) |
| Phase 8: Polish | 6 | T028–T033 |
| **Total** | **33** | |

---

## Notes

- [P] tasks touch different files — safe to run concurrently
- TDD: write test (RED) → confirm it fails → implement (GREEN) → clean up (REFACTOR)
- `GraphCanvas`, `graph-transformer.ts`, `useAgentRuns`, `hasCrudOperation` — do not modify
- `authFetch` from `@/lib/auth-fetch` — use for all approve/cancel API calls
- `runs-page.tsx` stays until T031 deprecation comment; delete in a follow-up cleanup PR after QA
