---
id: "037"
title: Agent Detail Page Correctness Review
stage: general
date: 2026-06-22
surface: agent
model: claude-sonnet-4-6
feature: none
branch: feat/dl-anomaly-detection
user: Dua Rizwan
command: /code-review (Angle A — line-by-line correctness)
labels: ["code-review", "correctness", "agents", "scheduler", "frontend", "bugs"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/agents.py
  - backend/app/services/sync/scheduler.py
  - frontend/src/hooks/use-agent-detail.ts
  - frontend/src/app/agents/[id]/page.tsx
tests:
  - none
---

## Prompt

You are doing a focused code review (Angle A: line-by-line correctness scan). I'll give you the key changed files for a feature that added an agent detail page at `/agents/[id]` with run history, pending approvals, KPIs, and Pause/Resume/Run controls. The data changes: `hired_agent_id` FK on `agent_runs`, new `GET /api/agents/{id}/runs` endpoint, scheduler tagging.

For every hunk, ask: what input, state, timing, or platform makes this line wrong? Look for: inverted/wrong conditions, null/undefined deref, missing await, falsy-zero checks, wrong-variable copy-paste, error swallowed in catch, unescaped regex metachars, off-by-one.

**FILE 1: backend/app/api/agents.py (the new endpoints)**

Key sections:

```python
# _get_recent_runs helper — used for GET /api/agents/{id} list view
async def _get_recent_runs(db: AsyncSession, user_id, agent_name: str, limit: int = 5) -> list[dict]:
    """Fetch recent agent runs that match the hired agent's intent."""
    result = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.user_id == user_id,
            AgentRun.intent.in_(["gmail", "github", "jira", "calendar", "slack"]),
        )
        .order_by(AgentRun.created_at.desc())
        .limit(limit)
    )
    runs = result.scalars().all()
    ...
```

```python
# GET /{agent_id}/runs — new detail endpoint
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

```python
# run_agent endpoint — manual trigger
@router.post("/{agent_id}/run", response_model=HiredAgentOut)
async def run_agent(...):
    agent = await _get_user_agent(agent_id, current_user, db)
    ...
    if agent.status == HiredAgentStatus.PAUSED:
        raise HTTPException(status_code=409, detail="Paused agents cannot run. Resume first.")

    now = datetime.now(timezone.utc)
    agent.status = HiredAgentStatus.RUNNING
    agent.last_run_at = now
    agent.last_error = None
    await db.commit()   # <-- commits RUNNING status before execute_workflow_run

    # Execute via existing workflow runner
    try:
        from app.services.workflow_runner import execute_workflow_run
        run_data = await execute_workflow_run(...)
        agent.status = HiredAgentStatus.ACTIVE
        agent.total_runs = (agent.total_runs or 0) + 1
        ...
        if run_data.get("status") == "failed":
            agent.status = HiredAgentStatus.FAILED
            agent.last_error = ...
    except Exception as exc:
        agent.status = HiredAgentStatus.FAILED
        agent.last_error = str(exc)[:500]

    # Schedule next run
    schedule = (agent.config or {}).get("schedule", "every_2_hours")
    agent.next_run_at = _schedule_to_next_run(schedule)
    await db.commit()
    await db.refresh(agent)
    return _serialize(agent)
```

**FILE 2: backend/app/services/sync/scheduler.py (_run_hired_agent)**

```python
async def _run_hired_agent(agent_id: UUID, user_id: UUID) -> None:
    ...
    async with AsyncSessionLocal() as db:
        agent = await db.get(HiredAgent, agent_id)
        if not agent or agent.status != HiredAgentStatus.ACTIVE:
            return
        ...
        now = datetime.now(timezone.utc)
        agent.status = HiredAgentStatus.RUNNING
        agent.last_run_at = now
        agent.last_error = None
        await db.commit()

        success = False
        try:
            run_data = await execute_workflow_run(...)
            # Tag the AgentRun with this hired agent's id
            if run_data.get("id"):
                from app.models.agent_run import AgentRun as AgentRunModel
                agent_run_row = await db.get(AgentRunModel, uuid.UUID(run_data["id"]))
                if agent_run_row:
                    agent_run_row.hired_agent_id = agent_id
                    await db.flush()
            agent.total_runs = (agent.total_runs or 0) + 1
            agent.status = HiredAgentStatus.ACTIVE
            ...
        except Exception as exc:
            agent.status = HiredAgentStatus.FAILED
            agent.last_error = str(exc)[:500]
        ...
        schedule = (agent.config or {}).get("schedule", "every_2_hours")
        agent.next_run_at = _schedule_to_next_run(schedule)
        await db.commit()
```

**FILE 3: frontend/src/hooks/use-agent-detail.ts**

```typescript
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
    ...
}
```

**FILE 4: frontend/src/app/agents/[id]/page.tsx**

```typescript
const successRate =
    agent && agent.total_runs > 0
        ? Math.round(
              (runs.filter((r) => r.status === "completed").length / agent.total_runs) * 100
          )
        : null;
```

```typescript
// RunHistoryChart
const days: { label: string; success: number; failed: number }[] = [];
const now = new Date();
for (let i = 29; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const dayRuns = runs.filter((r) => (r.created_at ?? "").startsWith(key));
    ...
}
```

```typescript
// Pending approvals buttons — no handler attached
<button className="...">Approve</button>
<button className="...">Deny</button>
```

Surface up to 6 candidates with file, approximate line number, one-line summary, and concrete failure scenario. Be specific about what input/state triggers the bug.

## Response snapshot

Delivered 6 confirmed bug candidates across the four files, each with file location, bug class, and a concrete trigger scenario. Findings covered: dead `agent_name` filter param in `_get_recent_runs`; stuck RUNNING state due to double-commit around `execute_workflow_run`; untruncated `error` field in `list_agent_runs` serialization; silent skip + ValueError in scheduler `hired_agent_id` tagging; success-rate denominator/numerator mismatch (lifetime vs. page-limited runs); and no-op Approve/Deny buttons with missing onClick handlers.

## Outcome

- Impact: 6 correctness defects identified across backend API, scheduler, and frontend — ranging from data silently not appearing in the detail page (BUG 1, 4) to permanently stuck agent state under infrastructure failure (BUG 2) to misleading KPI display (BUG 5) and non-functional UI controls (BUG 6).
- Tests: none run
- Files: none modified (read-only review)
- Next prompts: Fix BUG 4 (scheduler tagging) first — it blocks the entire runs list from populating. Then BUG 1 (_get_recent_runs filter). Then BUG 2 (RUNNING stuck state recovery). Then BUG 5 (success rate). Then BUG 6 (approval handlers).
- Reflection: Double-commit patterns around long-running async operations are a recurring correctness risk — the window between commits is a crash recovery blind spot worth adding a standard mitigation pattern for (e.g., a heartbeat or recovery job that resets stale RUNNING rows).

## Evaluation notes (flywheel)

- Failure modes observed: None — all 6 candidates are grounded in concrete input/state triggers with no speculation.
- Graders run and results (PASS/FAIL): Manual review only; no automated graders.
- Prompt variant (if applicable): Angle A (correctness-only scan) — no logic/style concerns included per scope.
- Next experiment (smallest change to try): Run Angle B (security/authz scan) over the same files, then Angle C (performance/N+1 queries).
