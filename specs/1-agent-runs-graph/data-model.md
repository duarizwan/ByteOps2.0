# Data Model: Action Center Redesign

**Branch**: `1-agent-runs-graph` | **Date**: 2026-05-31  
**Supersedes**: prior data-model.md (graph entities — kept below under "Preserved Entities")

---

## Backend Entities (existing — no changes)

### AgentRun (`backend/app/models/agent_run.py`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK → users | Auth-scoped |
| `intent` | String(50) | e.g. `"gmail"`, `"slack"` |
| `status` | AgentRunStatus enum | `planning` / `waiting_approval` / `running` / `completed` / `failed` / `cancelled` |
| `plan` | JSONB | Agent's execution plan |
| `final_response` | Text | Assistant's final reply |
| `error` | Text | Top-level error if run failed |
| `created_at` | DateTime TZ | Run start time |
| `completed_at` | DateTime TZ | Run end time (null if not done) |
| `steps` | Relationship → AgentRunStep[] | Ordered by `created_at ASC` |

### AgentRunStep (`backend/app/models/agent_run.py`)

| Field | Type | Notes |
|-------|------|-------|
| `id` | UUID | Primary key |
| `run_id` | UUID FK → agent_runs | Cascade delete |
| `step_type` | AgentRunStepType enum | `route` / `plan` / `tool_call` / `approval` / `verify` / `final` |
| `name` | String(255) | e.g. `"send_email"`, `"create_issue"` |
| `status` | String(50) | `"completed"` / `"failed"` / `"pending"` |
| `input` | JSONB | Step input payload (source of truth for `summarizeAction`) |
| `output` | JSONB | Step output payload |
| `error` | Text | Error message if step failed |
| `created_at` | DateTime TZ | Step execution time |

---

## New Frontend-Only Entities (Action Center)

### ActionSummary

Pure function output from `summarizeAction(run: AgentRun)`. Never persisted.

```typescript
interface ActionSummary {
  summary: string;   // e.g. "Sent email to alice@example.com"
  detail: string;    // e.g. "Subject: Q2 update"
}
```

**Derivation**: Find the first `AgentRunStep` where `step_type === "tool_call"` and `WRITE_VERBS.has(step.name.split("_")[0])`. Extract fields from `step.input` per the lookup table in the spec.

**Fallback**: `{ summary: "${run.intent} action completed", detail: humanize(step.name) }`

### ActionErrorCategory

Derived from `run.error` string. Used to select the fix CTA in `NeedsFixingCard`.

```typescript
type ActionErrorCategory =
  | "auth"       // run.error matches /401|403|token|expired|unauthorized/i
  | "timeout"    // run.error matches /timeout|503|api error/i
  | "unknown";   // fallback
```

### FilterTab

```typescript
type FilterTab = "all" | "pending" | "failed";
```

### ActionCenterState

State held at the `ActionCenter` component level.

```typescript
interface ActionCenterState {
  filterTab: FilterTab;          // active filter
  traceRunId: string | null;     // run ID for which TraceDrawer is open
  dismissedIds: Set<string>;     // client-side dismissed run IDs
}
```

### CategorizedRuns

Derived from the filtered `AgentRun[]` list. Computed inside `ActionCenter` via selectors.

```typescript
interface CategorizedRuns {
  pending: AgentRun[];    // status === "waiting_approval"
  failed: AgentRun[];     // status === "failed"
  history: AgentRun[];    // status === "completed" | "cancelled"
}
```

---

## Platform Badge Mapping

| `run.intent` | Badge label | Badge colour token |
|---|---|---|
| `gmail` | Gmail | `#EA4335` (inline — matches Google brand) |
| `slack` | Slack | `#4A154B` |
| `jira` | Jira | `#0052CC` |
| `github` | GitHub | `var(--foreground)` |
| `calendar` | Calendar | `#0F9D58` |
| `dropbox` | Dropbox | `#0061FF` |
| *(fallback)* | `run.intent` | `var(--muted-foreground)` |

---

## summarizeAction Lookup Table

`step.input` field names vary by tool. If a named field is missing, fall back to shorter string as noted.

| `run.intent` | `step.name` | `summary` | `detail` |
|---|---|---|---|
| `gmail` | `send_email` | `"Sent email to {input.to}"` | `"Subject: {input.subject}"` |
| `gmail` | `reply_to_email` | `"Replied to {input.thread_id ?? 'thread'}"` | `"To: {input.to}"` |
| `gmail` | `trash_email` | `"Trashed email: {input.subject}"` | `"{input.count ?? 1} message(s)"` |
| `gmail` | `create_draft` | `"Saved draft for {input.to}"` | `"Subject: {input.subject}"` |
| `calendar` | `create_event` | `"Created event: {input.title}"` | `"{input.date} · {input.attendees?.length ?? 0} people"` |
| `calendar` | `update_event` | `"Updated event: {input.title}"` | `"{input.updated_fields ?? 'details updated'}"` |
| `calendar` | `delete_event` | `"Deleted event: {input.title}"` | `"{input.date}"` |
| `slack` | `send_message` \| `post_message` | `"Posted to #{input.channel}"` | `"{(input.text ?? '').slice(0,60)}"` |
| `jira` | `create_issue` | `"Created {input.issue_type ?? 'issue'} {input.key ?? ''}"` | `"{input.summary}"` |
| `jira` | `update_issue` | `"Updated {input.key}"` | `"{input.updated_fields ?? 'fields updated'}"` |
| `jira` | `add_comment` | `"Commented on {input.key}"` | `"{(input.body ?? '').slice(0,60)}"` |
| `github` | `merge_pull_request` | `"Merged PR #{input.pull_number}"` | `"{input.title}"` |
| `github` | `create_issue` | `"Created issue #{input.number ?? ''}"` | `"{input.title}"` |
| `dropbox` | `upload_file` | `"Uploaded {input.filename}"` | `"to {input.path}"` |
| `dropbox` | `delete_file` | `"Deleted {input.filename}"` | `"{input.path}"` |
| `dropbox` | `move_file` | `"Moved {input.filename}"` | `"to {input.destination}"` |
| *(fallback)* | any | `"{run.intent} action completed"` | `humanize(step.name)` |

---

## Preserved Entities (Graph — unchanged, used inside TraceDrawer)

The `GraphNode`, `GraphEdge`, `GraphNodeType`, and `GraphNodeData` interfaces from the prior data-model.md remain valid. They are used exclusively inside `TraceDrawer → GraphCanvas`. See git history for the original definitions.
