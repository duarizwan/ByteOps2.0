---
id: "038"
title: Cross-file Hired Agent Run Trace
stage: general
date: 2026-06-22
surface: agent
model: claude-sonnet-4-6
feature: none
branch: feat/dl-anomaly-detection
user: Dua Rizwan
command: code-review (cross-file tracer)
labels: ["code-review","agents","hired-agent","bug","routes","migration"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/agents.py
  - backend/app/services/sync/scheduler.py
  - backend/app/services/workflow_runner.py
  - backend/app/services/agent_runtime.py
  - backend/app/models/agent_run.py
  - backend/app/models/hired_agent.py
  - backend/alembic/versions/0006_hired_agents.py
  - backend/alembic/versions/0007_agent_run_hired_agent_fk.py
tests:
  - none
---

## Prompt

You are doing a focused code review (Angle C: cross-file tracer). A feature added:
- `hired_agent_id` FK column on `agent_runs` table (migration 0007, model AgentRun)
- `GET /api/agents/{id}/runs` endpoint filtering by `AgentRun.hired_agent_id`
- Scheduler tagging: after execute_workflow_run, looks up the created AgentRun and sets hired_agent_id
- Hook `useAgentDetail` fetching both `/api/agents/{id}` and `/api/agents/{id}/runs`

Please trace these specific cross-file concerns:

Concern 1: Route ordering conflict — /templates vs /{agent_id}
Concern 2: execute_workflow_run return shape — does it return {"id": ...}?
Concern 3: run_agent endpoint does NOT tag hired_agent_id (manual trigger)
Concern 4: No ORM relationship HiredAgent -> AgentRun
Concern 5: Migration 0007 down_revision chain continuity

## Response snapshot

Traced all five concerns across agents.py, scheduler.py, workflow_runner.py, agent_runtime.py, agent_run.py, hired_agent.py, and both migrations.

**Findings:**

1. Route ordering — NOT A BUG. `/templates` is registered at line 348 before `/{agent_id}` at line 455. UUID type annotation also prevents "templates" from matching as an agent_id.

2. Return shape — NOT A BUG. `execute_workflow_run` ends with `return serialize_agent_run(...)`. `serialize_agent_run` in agent_runtime.py line 86 unconditionally emits `"id": str(run.id)`.

3. Manual run_agent missing hired_agent_id tag — **REAL BUG**. `run_agent` (agents.py lines 544–566) calls `execute_workflow_run` but never sets `hired_agent_id` on the resulting `AgentRun` row. The scheduler (`_run_hired_agent`, scheduler.py lines 293–298) does tag it. `GET /api/agents/{id}/runs` filters strictly on `hired_agent_id == agent_id`, so all manually-triggered runs are permanently invisible in the UI run history.

4. No ORM relationship — NOT A BUG. All query paths use explicit `select(AgentRun).where(...)` filters; no code traverses `agent.runs` as an ORM attribute. The FK index covers query performance.

5. Migration chain — NOT A BUG. 0006 has `down_revision = "0005_encrypt_tokens"`, 0007 has `down_revision = "0006"`. Chain is unbroken.

## Outcome

- Impact: Identified 1 confirmed bug: manually-triggered hired agent runs are never tagged with hired_agent_id, making them invisible in the GET /api/agents/{id}/runs response. Fix: add the same 3-line tagging block from scheduler.py to run_agent in agents.py after execute_workflow_run returns.
- Tests: none run
- Files: read-only trace, no files modified
- Next prompts: fix the run_agent tagging gap; optionally add runs relationship to HiredAgent model
- Reflection: Route ordering and migration chain were both clean. The one real bug is an asymmetry between the scheduled path and the manual path — the manual path just needs the same post-run tagging block.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment: n/a
