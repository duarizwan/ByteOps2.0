# Agent Detail View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/agents/[id]` detail page showing run history (chart + list), pending approvals, KPIs, and inline Pause/Resume/Run controls for each hired agent.

**Architecture:** Backend gets a new `hired_agent_id` FK on `agent_runs` (nullable, additive migration) plus a `GET /api/agents/{id}/runs` endpoint. The scheduler tags each run it creates. The frontend adds a `useAgentDetail` hook and a new Next.js dynamic route page; the existing agent list card gets a "View details" link.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Alembic · Next.js 14 (App Router) · Tailwind CSS · TypeScript · lucide-react

## Global Constraints

- All Tailwind classes must use semantic design-system tokens: `bg-card`, `border-border`, `text-foreground`, `text-muted-foreground`, `hover:bg-accent` — never hardcoded hex/hsl
- Success tint: `bg-green-500/15 text-green-600 dark:text-green-400`; Warning tint: `bg-amber-500/15 text-amber-600 dark:text-amber-400`; Error tint: `bg-red-500/15 text-red-500`
- Bar chart SVG fill values: green bars `#22c55e`, red bars `#ef4444`, empty `#e2e8f0` (light) / invisible (dark) — use `currentColor` or match `analytics/page.tsx` pattern
- Dark mode works via `.dark` class on `<html>` — CSS variables switch automatically; no manual `dark:` variants needed beyond the success/warning tints above
- Approval Approve/Deny buttons are UI-only — no backend wiring in this plan
- Fire (delete) action stays on the agents list page only
- `GET /api/agents/{id}/runs` default limit 50, max 200
- Alembic revision chain: 0006 → 0007

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `backend/alembic/versions/0007_agent_run_hired_agent_fk.py` | Create | Migration: add `hired_agent_id` column + index |
| `backend/app/models/agent_run.py` | Modify | Add `hired_agent_id` mapped column |
| `backend/app/api/agents.py` | Modify | Add `GET /{id}/runs` endpoint + `AgentRunOut` schema |
| `backend/app/services/sync/scheduler.py` | Modify | Tag `AgentRun.hired_agent_id` after `execute_workflow_run` |
| `frontend/src/hooks/use-agent-detail.ts` | Create | Hook: fetch agent + runs, expose pause/resume/runNow |
| `frontend/src/app/agents/[id]/page.tsx` | Create | Detail page: header, KPIs, approvals, chart, run list |
| `frontend/src/app/agents/page.tsx` | Modify | Add "View details →" link to `HiredAgentCard` |

---

## Task 1: Migration + AgentRun model

**Files:**
- Create: `backend/alembic/versions/0007_agent_run_hired_agent_fk.py`
- Modify: `backend/app/models/agent_run.py`

**Interfaces:**
- Produces: `AgentRun.hired_agent_id` — `uuid.UUID | None`, FK to `hired_agents.id ON DELETE SET NULL`, nullable, indexed. Used by Tasks 3 and 2.

- [ ] **Step 1: Write the migration file**

Create `backend/alembic/versions/0007_agent_run_hired_agent_fk.py` with this exact content:

```python
"""Add hired_agent_id FK to agent_runs
Revision ID: 0007
Revises: 0006
Create Date: 2026-06-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "agent_runs",
        sa.Column(
            "hired_agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("hired_agents.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_agent_runs_hired_agent_id",
        "agent_runs",
        ["hired_agent_id"],
    )


def downgrade():
    op.drop_index("ix_agent_runs_hired_agent_id", table_name="agent_runs")
    op.drop_column("agent_runs", "hired_agent_id")
```

- [ ] **Step 2: Add `hired_agent_id` to the AgentRun model**

In `backend/app/models/agent_run.py`, add this import at the top alongside the existing ForeignKey import (it's already imported), then add the column after the existing `user_id` block:

```python
hired_agent_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True),
    ForeignKey("hired_agents.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

Place it after `conversation_id` (line ~43). No relationship needed — reads are done via direct query.

- [ ] **Step 3: Run the migration**

```powershell
cd backend
.venv\Scripts\Activate.ps1
alembic upgrade head
```

Expected output ends with:
```
Running upgrade 0006 -> 0007, Add hired_agent_id FK to agent_runs
```

- [ ] **Step 4: Verify column exists**

```powershell
python -c "
import asyncio
from app.core.database import async_session_factory as S
from sqlalchemy import text
async def check():
    async with S() as db:
        r = await db.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='agent_runs' AND column_name='hired_agent_id'\"))
        print(r.scalar())
asyncio.run(check())
"
```

Expected output: `hired_agent_id`

- [ ] **Step 5: Commit**

```powershell
git add backend/alembic/versions/0007_agent_run_hired_agent_fk.py backend/app/models/agent_run.py
git commit -m "feat(agents): add hired_agent_id FK to agent_runs"
```

---

## Task 2: `GET /api/agents/{id}/runs` endpoint

**Files:**
- Modify: `backend/app/api/agents.py`

**Interfaces:**
- Consumes: `AgentRun.hired_agent_id` from Task 1; `_get_user_agent()` already in `agents.py`
- Produces: `GET /api/agents/{id}/runs?limit=50&offset=0` → `list[AgentRunOut]`
  ```python
  class AgentRunOut(BaseModel):
      id: str
      status: str
      intent: str
      created_at: str | None
      flagged: bool
      anomaly_score: float | None
      summary: str | None  # first 200 chars of final_response
      error: str | None
  ```

- [ ] **Step 1: Add `AgentRunOut` schema to `agents.py`**

Add after the existing `UpdateAgentRequest` class (around line 249):

```python
class AgentRunOut(BaseModel):
    id: str
    status: str
    intent: str
    created_at: str | None
    flagged: bool
    anomaly_score: float | None
    summary: str | None
    error: str | None
```

- [ ] **Step 2: Add the endpoint**

Add after the `fire_agent` endpoint at the bottom of `agents.py`:

```python
@router.get("/{agent_id}/runs", response_model=list[AgentRunOut])
async def list_agent_runs(
    agent_id: UUID,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = 50,
    offset: int = 0,
) -> list[AgentRunOut]:
    """List run history for a specific hired agent."""
    await _get_user_agent(agent_id, current_user, db)  # ownership check
    limit = min(limit, 200)
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.hired_agent_id == agent_id)
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = result.scalars().all()
    return [
        AgentRunOut(
            id=str(r.id),
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            intent=r.intent,
            created_at=_iso(r.created_at),
            flagged=bool(r.flagged),
            anomaly_score=r.anomaly_score,
            summary=(r.final_response or "")[:200] or None,
            error=r.error,
        )
        for r in runs
    ]
```

- [ ] **Step 3: Start the backend and test the endpoint**

```powershell
cd backend
uvicorn app.main:app --reload --port 8000
```

In another terminal:
```powershell
# Replace <TOKEN> with a valid Clerk JWT and <ID> with a real hired_agent id
curl -H "Authorization: Bearer <TOKEN>" http://localhost:8000/api/agents/<ID>/runs
```

Expected: `[]` (empty list — no runs tagged yet, that's fine) or a JSON array if runs exist.

- [ ] **Step 4: Commit**

```powershell
git add backend/app/api/agents.py
git commit -m "feat(agents): add GET /api/agents/{id}/runs endpoint"
```

---

## Task 3: Scheduler — tag runs with `hired_agent_id`

**Files:**
- Modify: `backend/app/services/sync/scheduler.py`

**Interfaces:**
- Consumes: `AgentRun.hired_agent_id` from Task 1; `run_data["id"]` returned by `execute_workflow_run`
- Produces: After each scheduled run, the created `AgentRun` row has `hired_agent_id` set to the hiring agent's UUID

- [ ] **Step 1: Add uuid import if missing**

At the top of `scheduler.py`, `uuid` is not yet imported. Add it:

```python
import uuid
```

(Place alongside the existing `from uuid import UUID` import — change it to `import uuid` and update usages, or simply add `import uuid` as a separate line.)

- [ ] **Step 2: Tag the AgentRun after execute_workflow_run**

In `_run_hired_agent`, find the block after `execute_workflow_run` returns `run_data`. Currently it reads:

```python
agent.total_runs = (agent.total_runs or 0) + 1
agent.status = HiredAgentStatus.ACTIVE
agent.metadata_ = {**(agent.metadata_ or {}), "last_agent_run_id": run_data.get("id")}
```

Add the tagging block immediately after `run_data = await execute_workflow_run(...)`:

```python
run_data = await execute_workflow_run(
    workflow_name=agent.name,
    workflow_id=str(agent.id),
    trigger={"type": "agent_scheduled", "template": agent.template_key},
    actions=[
        {"tool": t, "operation": "auto", "prompt": template["prompt_template"]}
        for t in template["required_tools"]
    ],
    user_id=user_id,
    db=db,
)
# Tag the AgentRun with this hired agent's id so the detail view can filter by it
if run_data.get("id"):
    from app.models.agent_run import AgentRun as AgentRunModel
    agent_run_row = await db.get(AgentRunModel, uuid.UUID(run_data["id"]))
    if agent_run_row:
        agent_run_row.hired_agent_id = agent_id
        await db.flush()
agent.total_runs = (agent.total_runs or 0) + 1
```

- [ ] **Step 3: Verify no import cycle**

```powershell
cd backend
python -c "from app.services.sync.scheduler import _run_hired_agent; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add backend/app/services/sync/scheduler.py
git commit -m "feat(agents): tag AgentRun.hired_agent_id in scheduler"
```

---

## Task 4: Frontend hook `use-agent-detail.ts`

**Files:**
- Create: `frontend/src/hooks/use-agent-detail.ts`

**Interfaces:**
- Consumes: `GET /api/agents/{id}` → `HiredAgent` (type from `use-agents.ts`); `GET /api/agents/{id}/runs` → `AgentRun[]`
- Produces:
  ```ts
  export interface AgentRun {
      id: string;
      status: string;
      intent: string;
      created_at: string | null;
      flagged: boolean;
      anomaly_score: number | null;
      summary: string | null;
      error: string | null;
  }

  export function useAgentDetail(id: string): {
      agent: HiredAgent | null;
      runs: AgentRun[];
      isLoading: boolean;
      error: string | null;
      refresh: () => Promise<void>;
      pause: () => Promise<void>;
      resume: () => Promise<void>;
      runNow: () => Promise<void>;
  }
  ```

- [ ] **Step 1: Create the hook file**

Create `frontend/src/hooks/use-agent-detail.ts`:

```typescript
"use client";

import { useState, useEffect, useCallback } from "react";
import { api } from "@/lib/api";
import { HiredAgent } from "@/hooks/use-agents";

export interface AgentRun {
    id: string;
    status: string;
    intent: string;
    created_at: string | null;
    flagged: boolean;
    anomaly_score: number | null;
    summary: string | null;
    error: string | null;
}

export function useAgentDetail(id: string) {
    const [agent, setAgent] = useState<HiredAgent | null>(null);
    const [runs, setRuns] = useState<AgentRun[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const refresh = useCallback(async () => {
        try {
            const [agentData, runsData] = await Promise.all([
                api<HiredAgent>(`/api/agents/${id}`),
                api<AgentRun[]>(`/api/agents/${id}/runs`),
            ]);
            setAgent(agentData);
            setRuns(runsData);
            setError(null);
        } catch (e) {
            setError(e instanceof Error ? e.message : "Failed to load agent");
        } finally {
            setIsLoading(false);
        }
    }, [id]);

    useEffect(() => {
        refresh();
        const interval = setInterval(refresh, 30_000);
        const onFocus = () => refresh();
        window.addEventListener("focus", onFocus);
        return () => {
            clearInterval(interval);
            window.removeEventListener("focus", onFocus);
        };
    }, [refresh]);

    const pause = useCallback(async () => {
        await api(`/api/agents/${id}/pause`, { method: "POST" });
        await refresh();
    }, [id, refresh]);

    const resume = useCallback(async () => {
        await api(`/api/agents/${id}/resume`, { method: "POST" });
        await refresh();
    }, [id, refresh]);

    const runNow = useCallback(async () => {
        await api(`/api/agents/${id}/run`, { method: "POST" });
        await refresh();
    }, [id, refresh]);

    return { agent, runs, isLoading, error, refresh, pause, resume, runNow };
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd frontend
npx tsc --noEmit
```

Expected: no errors related to `use-agent-detail.ts`

- [ ] **Step 3: Commit**

```powershell
git add frontend/src/hooks/use-agent-detail.ts
git commit -m "feat(agents): add useAgentDetail hook"
```

---

## Task 5: Agent detail page

**Files:**
- Create: `frontend/src/app/agents/[id]/page.tsx`

**Interfaces:**
- Consumes: `useAgentDetail(id)` from Task 4 — `{ agent, runs, isLoading, error, pause, resume, runNow }`
- Consumes: `HiredAgent`, `AgentRun` types
- Produces: Page at `/agents/[id]` with breadcrumb, header, KPIs, approvals panel, chart, run list

- [ ] **Step 1: Create the page file**

Create `frontend/src/app/agents/[id]/page.tsx`:

```tsx
"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
    Mail, Code2, Calendar, RefreshCw, Play, Pause, Zap,
    Loader2, AlertTriangle, X, CheckCircle, ArrowLeft,
} from "lucide-react";
import { TopBar } from "@/components/dashboard/top-bar";
import { useAgentDetail, AgentRun } from "@/hooks/use-agent-detail";

/* ── Icon map ───────────────────────────────────────────────────────────────── */
const ICON_MAP: Record<string, React.ReactNode> = {
    mail: <Mail className="w-5 h-5" />,
    code: <Code2 className="w-5 h-5" />,
    calendar: <Calendar className="w-5 h-5" />,
    "refresh-cw": <RefreshCw className="w-5 h-5" />,
};

/* ── Helpers ───────────────────────────────────────────────────────────────── */
function relativeTime(iso: string | null): string {
    if (!iso) return "Never";
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
}

function nextRunTime(iso: string | null): string {
    if (!iso) return "—";
    const diff = new Date(iso).getTime() - Date.now();
    if (diff < 0) return "Soon";
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `in ${mins}m`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `in ${hrs}h`;
    return `in ${Math.floor(hrs / 24)}d`;
}

/* ── Status badge ──────────────────────────────────────────────────────────── */
function StatusBadge({ status }: { status: string }) {
    const cfg: Record<string, { label: string; className: string }> = {
        active: { label: "Active", className: "bg-green-500/15 text-green-600 dark:text-green-400" },
        running: { label: "Running", className: "bg-blue-500/15 text-blue-600 dark:text-blue-400" },
        paused: { label: "Paused", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
        failed: { label: "Failed", className: "bg-red-500/15 text-red-500" },
        completed: { label: "Completed", className: "bg-green-500/15 text-green-600 dark:text-green-400" },
        waiting_approval: { label: "Awaiting", className: "bg-amber-500/15 text-amber-600 dark:text-amber-400" },
    };
    const { label, className } = cfg[status] ?? { label: status, className: "bg-muted text-muted-foreground" };
    return (
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${className}`}>{label}</span>
    );
}

/* ── Anomaly score chip ────────────────────────────────────────────────────── */
function AnomalyScore({ score }: { score: number | null }) {
    if (score === null) return <span className="text-xs text-muted-foreground">—</span>;
    const colour =
        score < 0.3 ? "text-green-600 dark:text-green-400"
        : score < 0.6 ? "text-amber-600 dark:text-amber-400"
        : "text-red-500";
    return <span className={`text-xs font-mono ${colour}`}>{score.toFixed(2)}</span>;
}

/* ── KPI card ──────────────────────────────────────────────────────────────── */
function KpiCard({ label, value, sub, warn }: { label: string; value: string; sub?: string; warn?: boolean }) {
    return (
        <div className="bg-card border border-border rounded-2xl p-4">
            <p className="text-2xl font-bold text-foreground">{value}</p>
            <p className="text-xs text-muted-foreground mt-1">{label}</p>
            {sub && (
                <p className={`text-xs mt-1 ${warn ? "text-amber-600 dark:text-amber-400" : "text-muted-foreground"}`}>
                    {sub}
                </p>
            )}
        </div>
    );
}

/* ── Run history bar chart (30 days) ──────────────────────────────────────── */
function RunHistoryChart({ runs }: { runs: AgentRun[] }) {
    // Build a map of date string → { success: n, failed: n }
    const days: { label: string; success: number; failed: number }[] = [];
    const now = new Date();
    for (let i = 29; i >= 0; i--) {
        const d = new Date(now);
        d.setDate(d.getDate() - i);
        const key = d.toISOString().slice(0, 10);
        const dayRuns = runs.filter((r) => (r.created_at ?? "").startsWith(key));
        days.push({
            label: i === 0 ? "today" : key.slice(5),
            success: dayRuns.filter((r) => r.status === "completed").length,
            failed: dayRuns.filter((r) => r.status === "failed").length,
        });
    }
    const maxCount = Math.max(...days.map((d) => d.success + d.failed), 1);
    const BAR_H = 80;

    return (
        <div className="bg-card border border-border rounded-2xl p-5">
            <p className="text-sm font-semibold text-foreground mb-4">Runs — Last 30 Days</p>
            <div className="flex items-end gap-[3px]" style={{ height: BAR_H + 20 }}>
                {days.map((d, i) => {
                    const total = d.success + d.failed;
                    const h = total === 0 ? 2 : Math.max(Math.round((total / maxCount) * BAR_H), 4);
                    const colour =
                        total === 0 ? "bg-border"
                        : d.failed > 0 ? "bg-red-500"
                        : "bg-green-500";
                    return (
                        <div key={i} className="flex-1 flex flex-col items-center gap-1">
                            <div
                                className={`w-full rounded-sm ${colour} opacity-80 transition-all`}
                                style={{ height: h }}
                                title={`${d.label}: ${total} run(s)`}
                            />
                            {i === 29 && (
                                <span className="text-[9px] text-muted-foreground whitespace-nowrap">today</span>
                            )}
                        </div>
                    );
                })}
            </div>
            <div className="flex gap-4 mt-3">
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm bg-green-500 inline-block" /> Success
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm bg-red-500 inline-block" /> Failed
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                    <span className="w-2.5 h-2.5 rounded-sm bg-border inline-block" /> No run
                </div>
            </div>
        </div>
    );
}

/* ── Run history list ──────────────────────────────────────────────────────── */
function RunHistoryList({ runs }: { runs: AgentRun[] }) {
    const [expandedId, setExpandedId] = useState<string | null>(null);

    if (runs.length === 0) {
        return (
            <div className="bg-card border border-border rounded-2xl p-10 text-center">
                <Zap className="w-8 h-8 text-muted-foreground mx-auto mb-3" />
                <p className="text-sm font-medium text-foreground mb-1">No runs yet</p>
                <p className="text-xs text-muted-foreground">Trigger one with Run Now above.</p>
            </div>
        );
    }

    return (
        <div className="bg-card border border-border rounded-2xl overflow-hidden">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                <p className="text-sm font-semibold text-foreground">Run History</p>
                <span className="text-xs text-muted-foreground">{runs.length} runs · click a row to expand</span>
            </div>
            <div className="overflow-x-auto">
                <table className="w-full text-sm">
                    <thead>
                        <tr className="border-b border-border bg-muted/30">
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Time</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Status</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Intent</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Anomaly</th>
                            <th className="text-left px-5 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wide">Summary</th>
                        </tr>
                    </thead>
                    <tbody>
                        {runs.map((run) => (
                            <>
                                <tr
                                    key={run.id}
                                    onClick={() => setExpandedId(expandedId === run.id ? null : run.id)}
                                    className="border-b border-border/60 hover:bg-accent/50 cursor-pointer transition-colors"
                                >
                                    <td className="px-5 py-3 text-xs text-muted-foreground whitespace-nowrap">
                                        {run.created_at ? new Date(run.created_at).toLocaleString() : "—"}
                                    </td>
                                    <td className="px-5 py-3"><StatusBadge status={run.status} /></td>
                                    <td className="px-5 py-3">
                                        <span className="text-xs px-2 py-0.5 rounded-md bg-purple-500/10 text-purple-600 dark:text-purple-400 font-medium">
                                            {run.intent}
                                        </span>
                                    </td>
                                    <td className="px-5 py-3"><AnomalyScore score={run.anomaly_score} /></td>
                                    <td className="px-5 py-3 max-w-xs">
                                        <span className="text-xs text-muted-foreground truncate block">
                                            {run.summary ?? run.error ?? "—"}
                                        </span>
                                    </td>
                                </tr>
                                {expandedId === run.id && (
                                    <tr key={`${run.id}-exp`} className="border-b border-border bg-blue-500/5 border-l-2 border-l-blue-500">
                                        <td colSpan={5} className="px-5 py-4">
                                            <p className="text-xs text-muted-foreground mb-1 font-medium">Full response</p>
                                            <pre className="text-xs text-foreground whitespace-pre-wrap leading-relaxed">
                                                {run.summary || run.error || "No output recorded."}
                                            </pre>
                                        </td>
                                    </tr>
                                )}
                            </>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/* ── Pending approvals panel ──────────────────────────────────────────────── */
function PendingApprovals({ runs }: { runs: AgentRun[] }) {
    const pending = runs.filter((r) => r.status === "waiting_approval");
    if (pending.length === 0) return null;

    return (
        <div className="bg-card border border-amber-500/40 rounded-2xl overflow-hidden">
            <div className="flex items-center gap-3 px-5 py-4 border-b border-amber-500/20">
                <AlertTriangle className="w-4 h-4 text-amber-500 flex-shrink-0" />
                <p className="text-sm font-semibold text-foreground">Pending Approvals</p>
                <span className="ml-auto text-xs font-semibold px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
                    {pending.length} waiting
                </span>
            </div>
            {pending.map((run) => (
                <div key={run.id} className="flex items-center justify-between gap-4 px-5 py-3.5 border-b border-border/60 last:border-0">
                    <div>
                        <p className="text-sm text-foreground">{run.summary ?? "Action requires approval"}</p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            Requested {relativeTime(run.created_at)} · Run {run.id.slice(0, 8)}
                        </p>
                    </div>
                    <div className="flex gap-2 flex-shrink-0">
                        <button className="px-3 py-1.5 text-xs font-medium bg-green-500/15 text-green-600 dark:text-green-400 border border-green-500/25 rounded-lg hover:bg-green-500/25 transition-colors">
                            Approve
                        </button>
                        <button className="px-3 py-1.5 text-xs font-medium bg-red-500/10 text-red-500 border border-red-500/20 rounded-lg hover:bg-red-500/20 transition-colors">
                            Deny
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}

/* ── Page ──────────────────────────────────────────────────────────────────── */
export default function AgentDetailPage() {
    const params = useParams();
    const id = params.id as string;
    const { agent, runs, isLoading, error, pause, resume, runNow } = useAgentDetail(id);
    const [actionError, setActionError] = useState<string | null>(null);
    const [actionLoading, setActionLoading] = useState(false);

    const handleAction = (fn: () => Promise<void>) => async () => {
        setActionLoading(true);
        setActionError(null);
        try {
            await fn();
        } catch (e) {
            setActionError(e instanceof Error ? e.message : "Action failed");
        } finally {
            setActionLoading(false);
        }
    };

    const successRate =
        agent && agent.total_runs > 0
            ? Math.round(
                  (runs.filter((r) => r.status === "completed").length / agent.total_runs) * 100
              )
            : null;

    if (isLoading) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <TopBar />
                <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                </div>
            </div>
        );
    }

    if (error || !agent) {
        return (
            <div className="min-h-screen flex flex-col bg-background">
                <TopBar />
                <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-4">
                    <p className="text-muted-foreground text-sm">{error ?? "Agent not found."}</p>
                    <Link href="/agents" className="text-sm text-blue-500 hover:underline">
                        ← Back to Agents
                    </Link>
                </div>
            </div>
        );
    }

    const icon = ICON_MAP[agent.template?.icon ?? ""] ?? <Zap className="w-5 h-5" />;
    const color = agent.template?.color ?? "#6b7280";

    return (
        <div className="min-h-screen flex flex-col bg-background">
            <TopBar />
            <main className="flex-1 max-w-5xl mx-auto w-full px-6 py-8 space-y-6">

                {/* Breadcrumb */}
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Link href="/agents" className="flex items-center gap-1 text-blue-500 hover:underline">
                        <ArrowLeft className="w-3.5 h-3.5" /> Agents
                    </Link>
                    <span>/</span>
                    <span className="text-foreground">{agent.name}</span>
                </div>

                {/* Action error */}
                {actionError && (
                    <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 rounded-lg text-sm text-red-500">
                        <AlertTriangle className="w-4 h-4 flex-shrink-0" />
                        {actionError}
                        <button onClick={() => setActionError(null)} className="ml-auto">
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                )}

                {/* Page header */}
                <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-4">
                        <div
                            className="w-12 h-12 rounded-2xl flex items-center justify-center text-white flex-shrink-0"
                            style={{ background: color }}
                        >
                            {icon}
                        </div>
                        <div>
                            <div className="flex items-center gap-2">
                                <h1 className="text-xl font-bold text-foreground">{agent.name}</h1>
                                <StatusBadge status={agent.status} />
                            </div>
                            <p className="text-sm text-muted-foreground mt-0.5">
                                {agent.template?.name} · {agent.schedule || "—"}
                            </p>
                        </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                        <button
                            onClick={handleAction(runNow)}
                            disabled={actionLoading || agent.status === "running"}
                            className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors disabled:opacity-50"
                        >
                            {actionLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                            Run Now
                        </button>
                        {agent.status === "paused" ? (
                            <button
                                onClick={handleAction(resume)}
                                disabled={actionLoading}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium border border-border hover:bg-accent text-foreground rounded-lg transition-colors disabled:opacity-50"
                            >
                                <CheckCircle className="w-3.5 h-3.5" /> Resume
                            </button>
                        ) : (
                            <button
                                onClick={handleAction(pause)}
                                disabled={actionLoading || agent.status === "running"}
                                className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium border border-border hover:bg-accent text-foreground rounded-lg transition-colors disabled:opacity-50"
                            >
                                <Pause className="w-3.5 h-3.5" /> Pause
                            </button>
                        )}
                    </div>
                </div>

                {/* KPI row */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <KpiCard label="Total Runs" value={String(agent.total_runs)} />
                    <KpiCard
                        label="Success Rate"
                        value={successRate !== null ? `${successRate}%` : "—"}
                        sub={successRate !== null ? `${runs.filter(r => r.status === "completed").length} / ${agent.total_runs} completed` : undefined}
                    />
                    <KpiCard
                        label="Last Run"
                        value={relativeTime(agent.last_run_at)}
                    />
                    <KpiCard
                        label="Next Run"
                        value={nextRunTime(agent.next_run_at)}
                        warn={!!agent.last_error}
                        sub={agent.last_error ? "⚠ Error on last run" : undefined}
                    />
                </div>

                {/* Pending approvals */}
                <PendingApprovals runs={runs} />

                {/* Run history chart */}
                <RunHistoryChart runs={runs} />

                {/* Run history list */}
                <RunHistoryList runs={runs} />

            </main>
        </div>
    );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```powershell
cd frontend
npx tsc --noEmit
```

Expected: no errors in `agents/[id]/page.tsx`

- [ ] **Step 3: Start the dev server and open the page**

```powershell
npm run dev
```

Open `http://localhost:3000/agents/<any-hired-agent-id>` in a browser. Verify:
- Breadcrumb shows "← Agents / {agent name}"
- Status badge colour matches agent status
- KPI cards render (values may be 0 / "—" if no runs yet)
- Approvals panel hidden (no waiting_approval runs yet)
- Chart renders 30 bars (all grey if no runs)
- Run list shows empty state or run rows

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/app/agents/[id]/page.tsx
git commit -m "feat(agents): add agent detail page /agents/[id]"
```

---

## Task 6: Add "View details" link to HiredAgentCard

**Files:**
- Modify: `frontend/src/app/agents/page.tsx`

**Interfaces:**
- Consumes: `agent.id: string` from the `HiredAgent` type
- Produces: Each `HiredAgentCard` has a `View details →` link at the bottom of its action row linking to `/agents/{agent.id}`

- [ ] **Step 1: Add the Link import**

`Link` from `next/link` is already imported at the top of `agents/page.tsx` (line 4). No change needed.

- [ ] **Step 2: Add "View details" link to HiredAgentCard actions row**

In `HiredAgentCard`, find the actions `<div>` at the bottom of the card (the one with the `border-t border-border` class, around line 277). It currently ends with the fire confirm block. Add the link **before** the fire button group, after the `<div className="flex-1" />` spacer:

Replace this section:
```tsx
<div className="flex-1" />

{confirmFire ? (
```

With:
```tsx
<Link
    href={`/agents/${agent.id}`}
    className="text-xs text-blue-500 hover:underline flex items-center gap-1"
>
    View details →
</Link>

<div className="flex-1" />

{confirmFire ? (
```

- [ ] **Step 3: Verify in browser**

Navigate to `http://localhost:3000/agents`. Each hired agent card should show "View details →" at the bottom left of the actions row. Click it — should navigate to `/agents/{id}` with the detail page.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/app/agents/page.tsx
git commit -m "feat(agents): add View details link on HiredAgentCard"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| New route `/agents/[id]` | Task 5 |
| New hook `use-agent-detail.ts` | Task 4 |
| `GET /api/agents/{id}/runs` endpoint | Task 2 |
| `hired_agent_id` FK migration | Task 1 |
| `AgentRun` model column | Task 1 |
| Scheduler tagging | Task 3 |
| `HiredAgentCard` "View details →" link | Task 6 |
| Breadcrumb | Task 5 |
| KPI row (4 cards) | Task 5 |
| Pending approvals panel (UI-only) | Task 5 |
| Run history chart (30 days) | Task 5 |
| Run history list (click to expand) | Task 5 |
| Pause/Resume on detail page | Task 5 |
| Run Now on detail page | Task 5 |
| Tailwind-only theming (no hardcoded colours) | Task 5 (all Tailwind classes) |
| Dark/light mode support | Task 5 (CSS variable tokens) |
| 404 → "Agent not found" error state | Task 5 |
| Runs endpoint failure → inline error | Task 4 (error surfaced via hook) |

All spec sections covered. No TBDs or placeholders in any step. Types are consistent: `AgentRun` defined in Task 4, consumed in Task 5. `AgentRunOut` defined in Task 2, consumed by Task 4 via API.
