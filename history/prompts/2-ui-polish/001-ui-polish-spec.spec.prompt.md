---
id: 001
title: UI Polish Spec — Chat Feedback, Badges, Errors, Loading
stage: spec
date: 2026-05-31
surface: agent
model: claude-sonnet-4-6
feature: 2-ui-polish
branch: 1-agent-runs-graph
user: Dua Rizwan
command: /sp.specify
labels: ["ui-polish","chat-feedback","status-badges","error-states","loading-transitions","spec"]
links:
  spec: specs/2-ui-polish/spec.md
  ticket: null
  adr: null
  pr: null
files:
  - specs/2-ui-polish/spec.md
  - specs/2-ui-polish/checklists/requirements.md
  - history/prompts/2-ui-polish/001-ui-polish-spec.spec.prompt.md
tests:
  - none
---

## Prompt

Resume ByteOps work — branch 1-agent-runs-graph.

Check memory for current state. We were mid-brainstorm on 4 UI improvements:
1. Chat progress feedback (stage labels during AI processing)
2. Activity items — status badges + better trace button
3. Graceful error states
4. Loading transitions for Action Center / trace view

A clarifying question was pending: for item #1, should progress labels appear (A) inline in the assistant bubble (replaces loading dots) or (B) as a status bar below the input? Answer: A (inline in assistant bubble — confirmed by model recommendation).

Pick up from there — write the design doc and move to implementation plan.

## Response snapshot

Spec written at `specs/2-ui-polish/spec.md` covering all 4 items:

- **P1** — Chat progress feedback: stage labels inline in assistant bubble driven by existing SSE events. "Understanding request…" → "Routing to specialist agent…" → "Waiting for approval…" → final text.
- **P2** — Activity status badges: Completed / Pending Approval / Failed / Waiting badges on ActionCard + prominent trace button.
- **P2** — Graceful error states: friendly messages for OAuth missing, no results, AI timeout, MCP unavailable, backend down — each with actionable links where relevant.
- **P3** — Loading transitions: skeleton placeholders for Action Center cards and trace view.

16 functional requirements (FR-001–016), 6 success criteria (SC-001–006), edge cases, assumptions, and out-of-scope defined. Checklist: all items pass.

## Outcome

- ✅ Impact: Spec produced for 4 UI polish improvements; ready for `/sp.plan`
- 🧪 Tests: none at spec stage
- 📁 Files: specs/2-ui-polish/spec.md, specs/2-ui-polish/checklists/requirements.md
- 🔁 Next prompts: /sp.plan or /superpowers:writing-plans
- 🧠 Reflection: Option A (inline bubble) was recommended by the model rather than provided by the user — documented in context. No [NEEDS CLARIFICATION] markers needed; all decisions were resolvable from context.

## Evaluation notes (flywheel)

- Failure modes observed: create-new-feature.ps1 script failed to run (execution policy + pwsh not found); manually created spec dir structure instead
- Graders run and results (PASS/FAIL): checklist validation — PASS
- Prompt variant (if applicable): none
- Next experiment: fix script execution to work without -ExecutionPolicy Bypass workaround
