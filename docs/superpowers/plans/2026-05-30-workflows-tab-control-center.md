# Workflows Tab Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the right-pane Workflows tab into a useful automation control center where users can see saved agentic automations, inspect recent runs, run them manually, pause or resume them, and understand when approval or connection attention is needed.

**Architecture:** Keep the existing `Workflow` model, `/api/workflows` API, `useWorkflows` hook, `WorkflowCard`, Agent Run runtime, and `/api/agent-runs` API. Add small backend payload fields for last run context, then improve the Workflows tab UI with richer cards, a details drawer, run history filtered by workflow, and an empty state that guides users toward creating their first automation.

**Tech Stack:** FastAPI, SQLAlchemy async models, existing Agent Runtime services, Next.js, React, Vitest, pytest.

---

## Current State

The project already has these workflow pieces:

1. Backend workflow model: `backend/app/models/workflow.py`
2. Backend workflow API: `backend/app/api/workflows.py`
3. Workflow runtime helper: `backend/app/services/workflow_runner.py`
4. Frontend workflow hook: `frontend/src/hooks/use-workflows.ts`
5. Right-pane workflow cards: `frontend/src/components/dashboard/context-panel.tsx`
6. Agent Run API and hook: `backend/app/api/agent_runs.py`, `frontend/src/hooks/use-agent-runs.ts`
7. Basic Agent Activity UI inside `context-panel.tsx`

The missing product layer is not another data model. The missing layer is a clear Workflows tab experience that shows automation health, control actions, and recent execution history in one place.

## In Scope

1. Enrich workflow API responses with `last_agent_run_id`, `last_run_status`, `last_run_summary`, `action_count`, and `needs_attention`.
2. Show richer workflow cards in the right pane.
3. Add a workflow detail drawer or expanded card state.
4. Show recent Agent Runs related to the selected workflow.
5. Show clear states for active, paused, running, failed, and waiting approval.
6. Keep the UI clean of marker characters such as asterisk, hyphen, and pipe.
7. Add focused backend and frontend tests.

## Out of Scope For This Slice

1. Full scheduled workflow engine.
2. Full visual workflow builder.
3. Real connector action execution for every workflow action.
4. Production database migration files, unless this repo already has a migration system available.

## File Structure

### Backend

1. Modify `backend/app/api/workflows.py`
   Add richer fields to `WorkflowOut` and `_serialize`.

2. Modify `backend/app/services/workflow_runner.py`
   Ensure workflow Agent Runs store `metadata.workflow_id` so frontend can filter runs by workflow.

3. Modify `backend/tests/test_workflows.py`
   Add tests for enriched workflow payload and workflow run metadata.

### Frontend

1. Modify `frontend/src/hooks/use-workflows.ts`
   Add new fields to `WorkflowItem`.

2. Modify `frontend/src/hooks/use-agent-runs.ts`
   Add helper for filtering runs by `metadata.workflow_id` if metadata is not currently typed.

3. Modify `frontend/src/components/dashboard/context-panel.tsx`
   Improve Workflows tab cards, add selected workflow details, and show related run history.

4. Modify `frontend/tests/context-panel.test.tsx`
   Add tests for enriched workflow UI, detail view, and clean text.

## Task 1: Enrich Workflow API Response

**Files:**
1. Modify `backend/app/api/workflows.py`
2. Modify `backend/tests/test_workflows.py`

**Purpose:** Give the frontend enough information to show automation health without extra guesswork.

- [ ] **Step 1: Add failing backend test**

Add this test to `backend/tests/test_workflows.py`:

```python
def test_serialize_workflow_includes_runtime_metadata():
    workflow = Workflow(
        id=uuid4(),
        user_id=uuid4(),
        name="Daily inbox triage",
        trigger={"type": "schedule", "label": "Every weekday at 9:00 AM"},
        actions=[
            {"tool": "gmail", "label": "Summarize unread important emails"},
            {"tool": "slack", "label": "Draft team update"},
        ],
        status=WorkflowStatus.ACTIVE,
        metadata_={
            "last_agent_run_id": "run-123",
            "last_plan": {
                "summary": "Run workflow: Daily inbox triage",
                "actions": ["Summarize unread important emails", "Draft team update"],
            },
            "last_run_status": "completed",
            "last_run_summary": "Workflow completed 2 actions.",
        },
    )

    payload = _serialize(workflow)

    assert payload.last_agent_run_id == "run-123"
    assert payload.last_run_status == "completed"
    assert payload.last_run_summary == "Workflow completed 2 actions."
    assert payload.action_count == 2
    assert payload.needs_attention is False
```

- [ ] **Step 2: Run the failing test**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest tests/test_workflows.py -q
```

Expected: FAIL because `WorkflowOut` does not expose these fields yet.

- [ ] **Step 3: Add fields to `WorkflowOut`**

In `backend/app/api/workflows.py`, extend `WorkflowOut`:

```python
class WorkflowOut(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    trigger: dict
    actions: list
    trigger_label: str
    action_summary: str
    action_count: int
    last_run_at: str | None
    next_run_at: str | None
    last_error: str | None
    last_agent_run_id: str | None = None
    last_run_status: str | None = None
    last_run_summary: str | None = None
    needs_attention: bool = False
    created_at: str | None = None
    updated_at: str | None = None
```

- [ ] **Step 4: Update `_serialize`**

In `backend/app/api/workflows.py`, update `_serialize`:

```python
def _serialize(workflow: Workflow) -> WorkflowOut:
    status_value = workflow.status.value if hasattr(workflow.status, "value") else str(workflow.status)
    metadata = workflow.metadata_ or {}
    last_run_status = metadata.get("last_run_status")
    last_run_summary = metadata.get("last_run_summary")
    needs_attention = (
        status_value in {"failed", "waiting_approval"}
        or bool(workflow.last_error)
        or last_run_status in {"failed", "waiting_approval", "cancelled"}
    )
    return WorkflowOut(
        id=str(workflow.id),
        name=_clean_activity_text(workflow.name) or workflow.name,
        description=_clean_activity_text(workflow.description),
        status=status_value,
        trigger=workflow.trigger or {},
        actions=workflow.actions or [],
        trigger_label=_trigger_label(workflow.trigger or {}),
        action_summary=_action_summary(workflow.actions or []),
        action_count=len(workflow.actions or []),
        last_run_at=_iso(workflow.last_run_at),
        next_run_at=_iso(workflow.next_run_at),
        last_error=_clean_activity_text(workflow.last_error),
        last_agent_run_id=metadata.get("last_agent_run_id"),
        last_run_status=metadata.get("last_run_status"),
        last_run_summary=_clean_activity_text(last_run_summary),
        needs_attention=needs_attention,
        created_at=_iso(workflow.created_at),
        updated_at=_iso(workflow.updated_at),
    )
```

- [ ] **Step 5: Run backend workflow tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest tests/test_workflows.py -q
```

Expected: PASS.

## Task 2: Persist Workflow Run Metadata Cleanly

**Files:**
1. Modify `backend/app/services/workflow_runner.py`
2. Modify `backend/app/api/workflows.py`
3. Modify `backend/tests/test_workflows.py`

**Purpose:** Make manual workflow runs connect clearly to Agent Runs.

- [ ] **Step 1: Add test for workflow run plan metadata**

Add this test to `backend/tests/test_workflows.py`:

```python
def test_build_workflow_run_plan_includes_workflow_id():
    plan = build_workflow_run_plan(
        workflow_name="Daily email brief",
        trigger={"type": "manual", "label": "Manual run"},
        actions=[{"tool": "gmail", "label": "Summarize unread important emails"}],
        workflow_id="workflow-123",
    )

    assert plan["workflow_id"] == "workflow-123"
    assert plan["summary"] == "Run workflow: Daily email brief"
```

- [ ] **Step 2: Update `build_workflow_run_plan` signature**

In `backend/app/services/workflow_runner.py`:

```python
def build_workflow_run_plan(
    workflow_name: str,
    trigger: dict,
    actions: list,
    workflow_id: str | None = None,
) -> dict:
    trigger_label = trigger.get("label") if isinstance(trigger, dict) else None
    action_labels: list[str] = []
    for action in actions:
        if isinstance(action, dict):
            action_labels.append(
                action.get("label") or action.get("name") or action.get("tool") or "Unnamed action"
            )
        elif isinstance(action, str):
            action_labels.append(action)
    return {
        "summary": f"Run workflow: {workflow_name}",
        "workflow_id": workflow_id,
        "trigger": trigger_label or "Manual run",
        "actions": action_labels,
        "blocked": False,
    }
```

- [ ] **Step 3: Update `execute_workflow_run`**

In `backend/app/services/workflow_runner.py`, pass `workflow_id` into the plan:

```python
plan = build_workflow_run_plan(workflow_name, trigger, actions, workflow_id=str(workflow_id))
```

When calling `create_agent_run`, include metadata:

```python
run = await create_agent_run(
    db,
    user_id=user_id,
    conversation_id=None,
    user_message_id=None,
    intent="workflow",
    plan=plan,
)
run.metadata_ = {"workflow_id": str(workflow_id)}
await db.commit()
await db.refresh(run)
```

- [ ] **Step 4: Update workflow metadata after manual run**

In `backend/app/api/workflows.py`, after `run_data = await execute_workflow_run(...)`, store:

```python
workflow.metadata_ = {
    **(workflow.metadata_ or {}),
    "last_agent_run_id": run_data["id"],
    "last_plan": run_data.get("plan"),
    "last_run_status": run_data.get("status"),
    "last_run_summary": run_data.get("final_response"),
}
```

- [ ] **Step 5: Run backend tests**

Run:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest tests/test_workflows.py tests/test_agent_runtime.py -q
```

Expected: PASS.

## Task 3: Extend Frontend Workflow Types

**Files:**
1. Modify `frontend/src/hooks/use-workflows.ts`
2. Modify `frontend/src/hooks/use-agent-runs.ts`

**Purpose:** Let UI components safely read the enriched backend payload.

- [ ] **Step 1: Update `WorkflowItem`**

In `frontend/src/hooks/use-workflows.ts`, update the interface:

```ts
export interface WorkflowItem {
    id: string;
    name: string;
    description: string | null;
    status: "active" | "paused" | "running" | "failed" | "waiting_approval";
    trigger: Record<string, unknown>;
    actions: unknown[];
    trigger_label: string;
    action_summary: string;
    action_count: number;
    last_run_at: string | null;
    next_run_at: string | null;
    last_error: string | null;
    last_agent_run_id?: string | null;
    last_run_status?: string | null;
    last_run_summary?: string | null;
    needs_attention?: boolean;
    created_at?: string | null;
    updated_at?: string | null;
}
```

- [ ] **Step 2: Ensure `AgentRun` supports metadata**

In `frontend/src/hooks/use-agent-runs.ts`, ensure `AgentRun` has:

```ts
metadata?: Record<string, unknown> | null;
```

If the backend serializer does not currently return `metadata`, add it in `backend/app/services/agent_runtime.py`:

```python
"metadata": run.metadata_,
```

- [ ] **Step 3: Run TypeScript check or focused tests**

Run:

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

Expected: PASS.

## Task 4: Improve Workflow Card UI

**Files:**
1. Modify `frontend/src/components/dashboard/context-panel.tsx`
2. Modify `frontend/tests/context-panel.test.tsx`

**Purpose:** Make each workflow card show automation status at a glance.

- [ ] **Step 1: Add failing UI test**

In `frontend/tests/context-panel.test.tsx`, extend the existing workflow test so a workflow fixture includes:

```ts
action_count: 2,
last_agent_run_id: "run-123",
last_run_status: "completed",
last_run_summary: "Workflow completed 2 actions.",
needs_attention: false,
```

Add expectations:

```ts
expect(screen.getByText("2 actions")).toBeInTheDocument();
expect(screen.getByText("Workflow completed 2 actions.")).toBeInTheDocument();
expect(screen.getByText(/view run/i)).toBeInTheDocument();
```

- [ ] **Step 2: Update `WorkflowCard` display**

In `frontend/src/components/dashboard/context-panel.tsx`, inside `WorkflowCard`, derive:

```ts
const lastRunSummary = workflow.last_run_summary ? cleanActivityText(workflow.last_run_summary) : null;
const actionCountLabel = `${workflow.action_count ?? workflow.actions.length} action${(workflow.action_count ?? workflow.actions.length) === 1 ? "" : "s"}`;
```

Render these inside the card:

```tsx
<div className="flex items-center justify-between text-xs text-muted-foreground">
    <span>{actionCountLabel}</span>
    {workflow.last_agent_run_id && (
        <button className="text-primary hover:underline">
            View run
        </button>
    )}
</div>
{lastRunSummary && (
    <p className="text-xs text-muted-foreground line-clamp-2">{lastRunSummary}</p>
)}
```

- [ ] **Step 3: Add attention styling**

If `workflow.needs_attention` is true, add a subtle visual state:

```tsx
<div className={cn(
    "relative bg-card border rounded-xl p-3 group transition-all",
    workflow.needs_attention ? "border-destructive/40" : "border-border"
)}>
```

- [ ] **Step 4: Run frontend test**

Run:

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

Expected: PASS.

## Task 5: Add Workflow Details View

**Files:**
1. Modify `frontend/src/components/dashboard/context-panel.tsx`
2. Modify `frontend/tests/context-panel.test.tsx`

**Purpose:** Let users inspect what a workflow does without leaving the right pane.

- [ ] **Step 1: Add selected workflow state**

In `ContextPanel`, add:

```ts
const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(null);
const selectedWorkflow = workflows.find((w) => w.id === selectedWorkflowId) ?? null;
```

- [ ] **Step 2: Add details button to `WorkflowCard`**

Pass `onViewDetails` into `WorkflowCard`:

```tsx
<WorkflowCard
    key={workflow.id}
    workflow={workflow}
    onPause={() => pauseWorkflow(workflow.id)}
    onResume={() => resumeWorkflow(workflow.id)}
    onRunNow={() => runWorkflowNow(workflow.id)}
    onViewDetails={() => setSelectedWorkflowId(workflow.id)}
/>
```

Add the button:

```tsx
<button
    onClick={onViewDetails}
    className="h-7 px-2 rounded-lg flex items-center gap-1 text-xs bg-accent hover:bg-accent/80 text-foreground transition-colors"
>
    Details
</button>
```

- [ ] **Step 3: Render details panel**

Below the workflow list, render selected details:

```tsx
{selectedWorkflow && (
    <div className="mt-3 rounded-xl border border-border bg-card p-3 space-y-2">
        <div className="flex items-start justify-between gap-2">
            <div>
                <h4 className="text-sm font-medium">{cleanActivityText(selectedWorkflow.name)}</h4>
                <p className="text-xs text-muted-foreground">{cleanActivityText(selectedWorkflow.trigger_label)}</p>
            </div>
            <button
                onClick={() => setSelectedWorkflowId(null)}
                className="text-xs text-muted-foreground hover:text-foreground"
            >
                Close
            </button>
        </div>
        <div className="text-xs text-muted-foreground">
            <p className="text-foreground">Actions</p>
            <p>{cleanActivityText(selectedWorkflow.action_summary)}</p>
        </div>
        {selectedWorkflow.last_run_summary && (
            <div className="text-xs text-muted-foreground">
                <p className="text-foreground">Last result</p>
                <p>{cleanActivityText(selectedWorkflow.last_run_summary)}</p>
            </div>
        )}
    </div>
)}
```

- [ ] **Step 4: Add UI test**

In `frontend/tests/context-panel.test.tsx`, add:

```ts
fireEvent.click(screen.getByRole("button", { name: /details/i }));
expect(screen.getByText("Actions")).toBeInTheDocument();
expect(screen.getByText("Last result")).toBeInTheDocument();
fireEvent.click(screen.getByRole("button", { name: /close/i }));
expect(screen.queryByText("Last result")).not.toBeInTheDocument();
```

- [ ] **Step 5: Run frontend test**

Run:

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

Expected: PASS.

## Task 6: Show Workflow Related Agent Runs

**Files:**
1. Modify `frontend/src/components/dashboard/context-panel.tsx`
2. Modify `frontend/src/hooks/use-agent-runs.ts`
3. Modify `frontend/tests/context-panel.test.tsx`

**Purpose:** Show recent execution history for a selected workflow.

- [ ] **Step 1: Filter runs by workflow id**

Inside `ContextPanel`, derive:

```ts
const selectedWorkflowRuns = selectedWorkflow
    ? runs.filter((run) => run.metadata?.workflow_id === selectedWorkflow.id)
    : [];
```

- [ ] **Step 2: Render recent runs**

Inside the selected workflow details panel:

```tsx
{selectedWorkflowRuns.length > 0 && (
    <div className="text-xs text-muted-foreground">
        <p className="text-foreground">Recent runs</p>
        <div className="mt-1 space-y-1">
            {selectedWorkflowRuns.slice(0, 3).map((run) => (
                <div key={run.id} className="flex items-center justify-between gap-2">
                    <span>{cleanActivityText(run.final_response ?? run.plan?.summary ?? "Workflow run")}</span>
                    <span className={cn("w-2 h-2 rounded-full", runStatusDot(run.status))} />
                </div>
            ))}
        </div>
    </div>
)}
```

- [ ] **Step 3: Add `runStatusDot` helper**

In `context-panel.tsx`:

```ts
function runStatusDot(status: string): string {
    if (status === "completed") return "bg-emerald-500";
    if (status === "failed" || status === "cancelled") return "bg-destructive";
    if (status === "waiting_approval") return "bg-yellow-500";
    return "bg-primary";
}
```

- [ ] **Step 4: Add frontend test**

Mock `useAgentRuns` with a run whose metadata has the selected workflow id:

```ts
agentRunState.runs = [
    {
        id: "run-123",
        intent: "workflow",
        status: "completed",
        plan: { summary: "Run workflow: Daily inbox triage" },
        final_response: "Workflow completed 2 actions.",
        metadata: { workflow_id: "workflow-1" },
        steps: [],
        created_at: "2026-05-30T09:00:00.000Z",
    },
];
```

Expectation after opening details:

```ts
expect(screen.getByText("Recent runs")).toBeInTheDocument();
expect(screen.getByText("Workflow completed 2 actions.")).toBeInTheDocument();
```

- [ ] **Step 5: Run frontend test**

Run:

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

Expected: PASS.

## Task 7: Improve Empty State And Creation Path

**Files:**
1. Modify `frontend/src/components/dashboard/context-panel.tsx`
2. Optional: Modify `frontend/src/components/dashboard/chat-interface.tsx`

**Purpose:** The empty state should tell the user what to do next.

- [ ] **Step 1: Update Workflows empty state copy**

Replace the current empty state description with:

```tsx
description="Create one from chat, for example: Every morning, summarize Gmail and Slack, then list anything urgent."
```

- [ ] **Step 2: Add Ask AI shortcut**

If `ContextPanel` has access to the parent `onSendToAI`, add a button:

```tsx
<button
    onClick={() => onSendToAI?.("Create a workflow that summarizes Gmail and Slack every morning and lists urgent tasks.")}
    className="mt-3 h-8 px-3 rounded-lg bg-primary/10 text-primary text-xs hover:bg-primary/15 transition-colors"
>
    Create with AI
</button>
```

If `ContextPanel` does not receive that callback in the current app structure, skip the button and keep the improved copy only.

- [ ] **Step 3: Add frontend test**

In `frontend/tests/context-panel.test.tsx`:

```ts
fireEvent.click(screen.getByRole("button", { name: /workflows/i }));
expect(screen.getByText(/summarizes gmail and slack/i)).toBeInTheDocument();
```

- [ ] **Step 4: Run frontend test**

Run:

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

Expected: PASS.

## Final Verification

Run backend:

```powershell
& '.\backend\.venv\Scripts\python.exe' -m pytest tests/test_workflows.py tests/test_agent_runtime.py tests/test_agent_policy.py tests/test_chat_agent_run.py tests/test_chat_activity_notification.py -q
```

Run frontend:

```powershell
cd frontend
npm run test:run -- tests/context-panel.test.tsx
```

## Acceptance Criteria

1. Workflows tab clearly shows automation name, status, trigger, action count, action summary, last run, next run, last result, and attention state.
2. Manual workflow run creates or updates linked Agent Run metadata.
3. Workflow details view shows actions, last result, and recent runs for that workflow.
4. Users can pause, resume, run now, and inspect details without leaving the right pane.
5. Empty state explains how to create a workflow through chat.
6. No Activity pane workflow text displays asterisk, hyphen, or pipe marker characters.
7. Focused backend and frontend tests pass.

## Risks

1. If `metadata` is not returned by the Agent Run serializer, the frontend cannot filter runs by workflow. Add it before Task 6.
2. If multiple workflow runs are created quickly, polling may show stale data for up to 30 seconds. Call `refresh()` after manual run.
3. This plan improves the Workflows tab as an operations surface. It does not implement a full scheduled automation engine.

## ADR Suggestion

📋 Architectural decision detected: Workflows tab as automation control center backed by Agent Runs rather than a separate notification feed. Document reasoning and tradeoffs? Run `/sp.adr workflows-control-center`.
