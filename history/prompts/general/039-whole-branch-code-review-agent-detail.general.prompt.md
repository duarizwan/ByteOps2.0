---
id: "039"
title: Whole-Branch Code Review Agent Detail View
stage: general
date: 2026-06-22
surface: agent
model: claude-sonnet-4-6
feature: none
branch: feat/dl-anomaly-detection
user: Dua Rizwan
command: /sp.phr
labels: ["code-review", "agent-detail", "hired-agents", "agent-runs", "correctness", "security", "integration"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - none
tests:
  - none
---

## Prompt

You are doing a final whole-branch code review of the ByteOps agent detail view feature. This covers all 7 commits added in this feature.

**Project root:** `D:\OneDrive - Jonas Software\Dua Stuff\uni\Byteops\ByteOps-master`

**Read the final review package:** `.git\sdd\review-final-feature.diff`

**Feature summary:** Added an agent detail page at `/agents/[id]` showing run history (chart + list), pending approvals, KPIs, and inline Pause/Resume/Run controls. Data layer changes: `hired_agent_id` FK on `agent_runs`, new `GET /api/agents/{id}/runs` endpoint, scheduler tagging.

**Files changed:**
- `backend/alembic/versions/0007_agent_run_hired_agent_fk.py` — migration
- `backend/app/models/agent_run.py` — model column
- `backend/app/api/agents.py` — new endpoint + schema
- `backend/app/services/sync/scheduler.py` — run tagging
- `frontend/src/hooks/use-agent-detail.ts` — new hook
- `frontend/src/app/agents/[id]/page.tsx` — new detail page
- `frontend/src/app/agents/page.tsx` — "View details" link

**Known Minor items (already recorded, do NOT re-raise unless they are actually worse than Minor):**
- Detail page expanded row uses `bg-blue-500/5 border-l-blue-500` (hardcoded colour — no semantic token exists for this accent)
- Intent badge uses `bg-purple-500/10 text-purple-600 dark:text-purple-400` (no purple semantic token exists)
- `text-amber-500` on AlertTriangle in approvals header (should be `text-amber-600`)

**Review dimensions:**
1. **Correctness:** Any logic bugs? Edge cases missed? (e.g., null handling, empty states, type mismatches)
2. **Security:** Auth checks in place on new endpoint? No data leakage?
3. **Integration:** Do the pieces connect correctly — scheduler tagging → endpoint filtering → hook fetching → page rendering?
4. **Spec compliance:** Any spec requirements missing across the whole feature?
5. **Code quality:** Duplication, unnecessary complexity, anything that would confuse a future developer?

**Return:**
- Overall verdict: Ready to merge / Needs fixes
- Findings by dimension (Critical / Important / Minor)
- One-line summary

## Response snapshot

Ran a full 7-angle parallel review (line-by-line scan, removed-behavior audit, cross-file tracer, reuse, simplification, efficiency, altitude) followed by individual verification agents for each candidate. All 5 top candidates were CONFIRMED. Verdict: **Needs fixes** — 3 blocking issues before merge.

8 ranked findings were returned:

1. **Critical** — `POST /agents/{id}/run` never sets `hired_agent_id` on the created AgentRun; all manually-triggered runs are permanently invisible in the run history tab (`agents.py:1781`).
2. **Critical** — `_get_recent_runs` ignores its `agent_name` parameter and returns cross-agent runs via a hardcoded intent whitelist; `GET /agents/{id}` returns wrong `recent_runs` for every agent (`agents.py:1557`).
3. **Important** — Approve/Deny buttons in `PendingApprovals` have no `onClick` handlers — non-functional stubs with no backend endpoint (`page.tsx:240`).
4. **Important** — Agent can get permanently stuck in `RUNNING` status if process crashes between two `db.commit()` calls; scheduler skips RUNNING agents with no watchdog (`agents.py:1773`).
5. **Important** — Success rate KPI divides page-limited completions (max 50) by `agent.total_runs` (lifetime), systematically understating rate for agents with >50 runs (`page.tsx:274`).
6. **Minor** — `daily_evening` and `weekdays_morning` schedules both produce `timedelta(days=1)` from now, causing schedule drift from the user's expected fire time (`agents.py:1504`).
7. **Minor** — RunHistoryChart groups runs by raw ISO string prefix rather than normalised UTC date, misassigning runs near midnight for non-UTC offsets (`page.tsx:93`).
8. **Minor** — Scheduler's post-hoc `hired_agent_id` tagging is silently dropped if `execute_workflow_run` raises before returning `run_data` (`scheduler.py:293`).

Security: all new endpoints properly guarded via `get_current_clerk_user` + `_get_user_agent` ownership check. No data leakage found.

## Outcome

- ✅ Impact: Identified 3 blocking correctness bugs (manual runs invisible, wrong recent_runs on detail endpoint, non-functional approval buttons) and 5 additional issues across correctness, reliability, and code quality. Feature should not merge until the top 3 are resolved.
- 🧪 Tests: none run — read-only review
- 📁 Files: none modified — read-only review
- 🔁 Next prompts: Fix the three Critical/Important issues — add `hired_agent_id` tagging to `run_agent`, rewrite `_get_recent_runs` to filter by `hired_agent_id`, and either wire the Approve/Deny buttons to a backend endpoint or hide them if the feature is out of scope.
- 🧠 Reflection: The post-hoc tagging pattern in the scheduler was the right shape but was only applied to one of two call sites (scheduler vs. manual trigger). The correct fix is upstream: pass `hired_agent_id` into `execute_workflow_run` so it cannot be accidentally omitted. Whenever a FK is used for filtering in one endpoint, every code path that creates the FK-target row must set it.

## Evaluation notes (flywheel)

- Failure modes observed: PHR agents 037 and 038 were created by sub-agents during the review itself (not by the user request), so there is a minor ID collision risk if the user also runs `/sp.phr` immediately after. The next allocated ID (039) correctly skips those.
- Graders run and results (PASS/FAIL): All 5 CONFIRMED — 5/5 PASS. 0 REFUTED.
- Prompt variant (if applicable): max-effort parallel 7-angle review with individual verification agents per candidate
- Next experiment (smallest change to try): Parameterise `execute_workflow_run` to accept an optional `hired_agent_id` argument so both the scheduler and manual-trigger paths set it at creation time rather than backfilling post-hoc.
