# Agent Detail View — Design Spec

**Date:** 2026-06-22  
**Branch:** feat/dl-anomaly-detection  
**Status:** Approved

---

## 1. Goal

Add a dedicated detail page for each hired agent at `/agents/[id]` that shows run history (chart + list), pending approvals, live KPIs, and inline controls — so users can monitor and manage a single agent without leaving to the list.

---

## 2. Scope

**In scope:**
- New route `frontend/src/app/agents/[id]/page.tsx`
- New hook `frontend/src/hooks/use-agent-detail.ts`
- New backend endpoint `GET /api/agents/{id}/runs`
- Alembic migration: add `hired_agent_id` FK to `agent_runs`
- `AgentRun` model: add `hired_agent_id` column
- Scheduler: tag new runs with `hired_agent_id`
- `HiredAgentCard` on list page: add "View details →" link

**Out of scope:**
- Fire (delete) action on the detail page — stays on the list
- Editing agent config from the detail page
- Real-time push (SSE/WebSocket) — polling at 30s is sufficient
- Approval action backend endpoints (approvals are displayed only; approve/deny wired up in a future task)

---

## 3. Data Layer

### 3a. Migration
New Alembic migration `0007_agent_run_hired_agent_fk.py`:
```sql
ALTER TABLE agent_runs
  ADD COLUMN hired_agent_id UUID REFERENCES hired_agents(id) ON DELETE SET NULL;
CREATE INDEX ix_agent_runs_hired_agent_id ON agent_runs(hired_agent_id);
```
Existing rows remain NULL — no backfill needed.

### 3b. AgentRun model
Add to `backend/app/models/agent_run.py`:
```python
hired_agent_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("hired_agents.id", ondelete="SET NULL"), nullable=True, index=True
)
```

### 3c. Scheduler tagging
In `backend/app/services/sync/scheduler.py`, `_run_hired_agent`: when creating/updating the `AgentRun` record, set `agent_run.hired_agent_id = hired_agent.id`.

### 3d. New endpoint
```
GET /api/agents/{id}/runs?limit=50&offset=0
```
- Auth: current user must own the agent (reuse `_get_user_agent`)
- Query: `AgentRun` where `hired_agent_id = id`, ordered by `created_at DESC`
- Response fields per run: `id, status, intent, created_at, flagged, anomaly_score, final_response (truncated to 200 chars), error`
- Default limit: 50, max: 200

---

## 4. Frontend

### 4a. Hook: `use-agent-detail.ts`
```ts
useAgentDetail(id: string) → { agent, runs, isLoading, error, refresh, pause, resume, runNow }
```
- Calls `GET /api/agents/{id}` + `GET /api/agents/{id}/runs` in parallel
- Polls every 30s + focus refresh (same pattern as `use-agents.ts`)
- `pause`, `resume`, `runNow` call the existing endpoints and trigger `refresh`

### 4b. Page: `/agents/[id]/page.tsx`

**Sections (top → bottom):**

1. **Breadcrumb** — `← Agents` link back to `/agents`

2. **Page header**
   - Agent icon (colored, from template) + name + status badge + template name + schedule
   - Right side: `Run Now` (primary blue) + `Pause` / `Resume` (ghost) buttons
   - Disabled + spinner while `status === "running"`

3. **KPI row** — 4 cards:
   - Total Runs
   - Success Rate (`completed / total_runs * 100`, shown as `XX%`)
   - Last Run (relative time + duration placeholder)
   - Next Run (relative time + amber warning if `last_error` is set)

4. **Pending Approvals panel** — shown only when `recent_runs` contains entries with `status === "waiting_approval"`. Amber border card. Each item shows description + "Requested X ago · Run #N" + Approve / Deny buttons (buttons are UI-only for now, wired in future task).

5. **Run history chart** — inline SVG bar chart, 30 days. Each bar height = run count that day, colour = green if all succeeded, red if any failed, grey if zero runs. Labels: "today" on rightmost bar.

6. **Run history list** — scrollable table, last 50 runs:
   - Columns: Time · Status badge · Intent pill · Anomaly score (coloured: green <0.3, amber 0.3–0.6, red >0.6) · Summary snippet
   - Click a row → inline expand showing full `final_response` text
   - Empty state: "No runs yet — trigger one with Run Now"

### 4c. List page change
`HiredAgentCard` gets a `View details →` text link at the bottom of the actions row, linking to `/agents/{agent.id}`.

---

## 5. Theming

The project uses Tailwind CSS with CSS custom property tokens defined in `globals.css`. All components must use **only** these semantic Tailwind classes — never hardcoded hex or hsl values:

| Purpose | Class |
|---|---|
| Page background | `bg-background` |
| Card surface | `bg-card border border-border` |
| Primary text | `text-foreground` |
| Secondary text | `text-muted-foreground` |
| Hover states | `hover:bg-accent` |
| Blue primary action | `bg-blue-600 hover:bg-blue-700 text-white` |
| Success tint | `bg-green-500/15 text-green-600 dark:text-green-400` |
| Warning tint | `bg-amber-500/15 text-amber-600 dark:text-amber-400` |
| Destructive tint | `bg-red-500/15 text-red-500` |

The **bar chart** must use Tailwind colour values via inline `fill` attributes (matching `analytics/page.tsx` pattern): green bars use `#22c55e` (Tailwind `green-500`), red bars use `#ef4444` (Tailwind `red-500`), empty bars use the current border colour read from a CSS variable. Chart container uses `bg-card border border-border rounded-2xl`.

Dark mode is applied via the `.dark` class on `<html>` — no manual dark: variants needed on most elements since the CSS variables switch automatically.

---

## 6. Navigation

TopBar already has an "Agents" link to `/agents`. No TopBar changes needed.

---

## 7. Error handling

- If `GET /api/agents/{id}` returns 404 → show "Agent not found" with a back link
- If `GET /api/agents/{id}/runs` fails → show run list error state inline (chart and KPIs still render)
- Pause/resume/runNow errors → inline banner below header (same pattern as agents list page)

---

## 8. Acceptance criteria

- [ ] `/agents/[id]` renders with correct agent name, status, and KPIs
- [ ] Run history chart shows 30 days with correct green/red/grey colouring
- [ ] Run history list shows up to 50 runs; clicking a row expands the full response
- [ ] Pending approvals panel is visible only when waiting_approval runs exist
- [ ] Run Now triggers a run and the list refreshes within 30s
- [ ] Pause/Resume updates status badge without full page reload
- [ ] New runs created by the scheduler are tagged with `hired_agent_id`
- [ ] `hired_agent_id` migration applies cleanly; existing rows unaffected
- [ ] `HiredAgentCard` "View details →" link navigates to the correct detail page
