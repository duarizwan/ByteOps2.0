# Future Work: Agent-as-a-Service Pivot

> Status: **Planned (not started)** — design agreed on 2026-06-13, parked for future implementation.
> Origin: brainstorming session on pivoting ByteOps from a SaaS copilot dashboard to an "Agent as a Service" product.

## Decision summary

ByteOps pivots to a service where users **hire autonomous agents** that work in their connected tools. Chosen model: **"hire an agent" outcome service** (Option A) — not a developer API platform, not a white-label embed.

Key decisions made:

| Decision | Choice |
|---|---|
| Business goal | Real product attempt (paying customers eventually) |
| Constraints | Solo founder, launch ASAP — ruthlessly reuse existing codebase |
| Launch agents | **Inbox Triage Agent** + **Dev Standup Agent** |
| Fast-follow agents | Meeting Prep Agent, Task Sync Agent |
| Billing at launch | **Free** (validate demand first; leave room for a `plan` field so Stripe bolts on later) |
| Existing chat UX | **Kept as-is** — agents are an addition alongside the current chat-first dashboard, not a replacement |

## 1. Product definition

- **Inbox Triage Agent** — periodically reviews new Gmail, classifies/labels, summarizes important threads, drafts replies, escalates urgent items to Slack/notifications. Risky actions (e.g., sending email) go through the existing approval gates.
- **Dev Standup Agent** — daily scheduled digest of GitHub PR/commit activity + Jira ticket movement, posted to a chosen Slack channel; flags stale PRs.

## 2. Backend architecture (mostly reuse)

**New concept: Agent Template + Hired Agent.**
- Templates are **code-defined constants** (Python dicts: name, description, required tools, default schedule, prompt/policy bundle) — not DB rows. A DB table buys nothing until templates are user-editable.
- New table `hired_agents`: `id, user_id, template_key, config (JSONB: schedule, slack_channel, triage rules…), status (active/paused), created_at`. One Alembic migration.

**Runtime: zero new engines.** A hired agent is executed by the existing `workflow_runner` + APScheduler path — each active `hired_agent` registers a scheduled job that builds a plan (via existing `agent_planner`/`agent_policy`) and runs through the existing `agent_run` ledger, steps, and approval gates. Inbox Triage piggybacks on the existing `gmail_sync`; Dev Standup is a pure scheduled run using the existing GitHub/Jira/Slack MCP servers.

**New API surface (one new router, `app/api/agents.py`):**
- `GET /api/agents/templates` — list available templates + required tools
- `POST /api/agents` — hire (validates required tool connections exist)
- `GET /api/agents`, `PATCH /api/agents/{id}` (pause/resume/config), `DELETE /api/agents/{id}`
- `POST /api/agents/{id}/run` — manual trigger
- Runs/approvals reuse the existing `/api/agent-runs` endpoints unchanged.

## 3. Frontend

One new section; existing pages untouched:
- **`/agents` page** — "My Agents" grid + template gallery. Hire flow is a 3-step wizard: pick template → connect missing tools (reuses `ToolConnectionsProvider` + OAuth flows) → configure (schedule, Slack channel) → activate.
- **Agent detail view** — status, recent runs (reuses existing runs components/graph), pending approvals, pause/edit/fire.
- **Landing page copy** repositioned around "hire your first agent free" — same design system.
- New hooks `use-agents.ts` following existing hook patterns.

## 4. Hardening folded in (launch blockers from the 2026-06-13 audit)

Real users will connect their actual Gmail, so these become launch blockers:
1. Add `backend/.env` to `.gitignore` and rotate all keys (file is currently untracked but **not ignored**).
2. Input validation limits on chat message length, workflow action counts, and agent-config payloads.
3. Tighten CORS (no wildcard methods/headers in `app/main.py`).
4. Switch prod startup from `Base.metadata.create_all` to `alembic upgrade head`.

Remaining audit items (error-handling rewrite in `chat.py`, splitting `context-panel.tsx`, polling → SSE for notifications, middleware → proxy migration, aria-live on chat stream) stay post-launch.

## 5. Error handling & trust

- Agent run failure → notification + red status on agent card with the failure reason (no silent failures).
- Expired OAuth token → agent auto-pauses with a "reconnect <tool>" call-to-action.
- Every agent action is visible in run history; destructive/external actions require approval — the audit-and-approve story **is** the product's trust pitch.

## 6. Testing

- Unit: triage classification prompts/parsing, standup digest assembly, hire-flow validation (missing tool connections rejected).
- Integration: one happy-path test per template through the runner with mocked MCP tools.
- Manual demo script per agent before launch.

## 7. Out of scope for v1

Billing/Stripe, Meeting Prep + Task Sync agents, public developer API, white-label/embedding, teams/multi-user workspaces, custom user-built templates.

## Next steps when picked up

1. Re-validate this design against the codebase state at that time.
2. Run `/sp.specify` (or the writing-plans skill) to turn this into a spec + dependency-ordered implementation plan.
3. Implement hardening items (section 4) first — they are independent of the pivot and worth doing regardless.
