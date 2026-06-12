---
id: 019
title: Agent-as-a-service pivot design parked as future work
stage: general
date: 2026-06-13
surface: agent
model: claude-fable-5
feature: none
branch: main
user: Dua Rizwan
command: none
labels: ["brainstorming","product-pivot","agent-as-a-service","future-work"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - docs/FUTURE_WORK.md (created)
tests:
 - none (design documentation only)
---

## Prompt

i want to make this project agent as a service instead of saas

(follow-ups in same session: "A would be fine then" — choosing the "hire an agent" model; template/scope/billing/UX answers via structured questions; "now create an md file and store it as future work")

## Response snapshot

Ran brainstorming skill. Clarified via one-question-at-a-time flow: goal = real product attempt; constraints = solo founder, launch ASAP; chosen model = Option A "hire an agent" outcome service (vs developer API platform or white-label embed); launch agents = Inbox Triage + Dev Standup (Meeting Prep + Task Sync fast-follow); billing = free at launch; existing chat-first dashboard kept as-is with agents added alongside. Presented full design: code-defined agent templates + new `hired_agents` table, execution through existing workflow_runner/APScheduler/agent_run ledger/approval gates (zero new engines), new `app/api/agents.py` router, new `/agents` frontend page with 3-step hire wizard, security hardening items from the 2026-06-13 audit folded in as launch blockers. User chose to park the design as future work instead of proceeding to implementation — saved to docs/FUTURE_WORK.md.

## Outcome

- ✅ Impact: Pivot design fully captured in docs/FUTURE_WORK.md with decisions, architecture, scope boundaries, and pickup instructions; no code changed.
- 🧪 Tests: none
- 📁 Files: docs/FUTURE_WORK.md created
- 🔁 Next prompts: when resuming — /sp.specify from FUTURE_WORK.md; implement hardening items (gitignore/.env, validation, CORS, alembic) which are worthwhile regardless of pivot
- 🧠 Reflection: User redirected from the skill's spec→plan flow to parking the design; respected user instruction over skill default (no commit, no implementation plan).

## Evaluation notes (flywheel)

- Failure modes observed: user selected all 4 templates when asked for up to 2; resolved with an explicit phasing question.
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): N/A
