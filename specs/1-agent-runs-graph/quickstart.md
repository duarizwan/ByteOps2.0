# Quickstart: Action Center Development

**Branch**: `1-agent-runs-graph` | **Date**: 2026-05-31

---

## Prerequisites

- Node.js 20+ with pnpm / npm
- Python 3.10+ with `uv`
- `.env.local` in `frontend/` (Clerk keys + backend URL)
- `.env` in `backend/` (database URL + Clerk secret)

---

## Start the Dev Environment

```bash
# Terminal 1 — Backend
cd backend
uv run uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

App runs at `http://localhost:3000`. Action Center page at `http://localhost:3000/runs`.

---

## Key Files for This Feature

### Frontend (new/changed)

| File | Status | Purpose |
|------|--------|---------|
| `frontend/src/components/runs/action-center.tsx` | NEW | Top-level page shell (replaces `runs-page.tsx`) |
| `frontend/src/components/runs/action-card.tsx` | NEW | Completed/cancelled run card |
| `frontend/src/components/runs/awaiting-approval-card.tsx` | NEW | Pending approval card with Approve/Cancel/Edit |
| `frontend/src/components/runs/needs-fixing-card.tsx` | NEW | Failed run card with error + fix CTA |
| `frontend/src/components/runs/trace-drawer.tsx` | NEW | Slide-in drawer wrapping GraphCanvas |
| `frontend/src/components/runs/filter-tabs.tsx` | NEW | All / Pending / Failed tab bar |
| `frontend/src/lib/summarize-action.ts` | NEW | Pure function: `summarizeAction(run) → {summary, detail}` |
| `frontend/src/app/(dashboard)/runs/page.tsx` | UPDATE | Replace `<RunsPage />` import with `<ActionCenter />` |

### Frontend (unchanged — do not modify)

| File | Reason |
|------|--------|
| `frontend/src/components/runs/graph-canvas.tsx` | Reused inside TraceDrawer |
| `frontend/src/components/runs/graph-nodes/ellipse-node.tsx` | Reused inside TraceDrawer |
| `frontend/src/lib/graph-transformer.ts` | Reused inside TraceDrawer |
| `frontend/src/hooks/use-agent-runs.ts` | Unchanged — still polls every 30s |

### Backend (no changes needed for Phase 1)

| File | Notes |
|------|-------|
| `backend/app/api/agent_runs.py:67` | `POST /{id}/approve` — already exists |
| `backend/app/api/agent_runs.py:155` | `POST /{id}/cancel` — already exists |

---

## Running Tests

```bash
# Frontend unit tests
cd frontend
npm run test

# Run a specific test file
npm run test -- summarize-action.test.ts

# Backend tests
cd backend
uv run pytest
```

---

## Calling Approve / Cancel from the Frontend

Both endpoints are auth-gated via Clerk. Use the existing `authFetch` helper:

```typescript
import { authFetch } from "@/lib/auth-fetch";

// Approve
await authFetch(`/api/agent-runs/${runId}/approve`, { method: "POST" });

// Cancel
await authFetch(`/api/agent-runs/${runId}/cancel`, { method: "POST" });
```

Both return `{ status: "approved" | "cancelled", run_id: string }` on success.
409 means the run is no longer in `waiting_approval` — treat as a stale card (refresh the list).

---

## Checking the Data Shape

To inspect a real run's step input payloads (needed for `summarizeAction` development):

```bash
# In the backend shell
uv run python -c "
from app.core.database import get_db_sync
from app.models.agent_run import AgentRun
import json
# Query your DB here to inspect run.steps[*].input
"
```

Or via the API:
```
GET http://localhost:8000/api/agent-runs/{id}
Authorization: Bearer <your-clerk-token>
```
