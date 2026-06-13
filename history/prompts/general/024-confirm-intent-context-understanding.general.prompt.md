---
id: 024
title: Confirm intent context understanding behavior
stage: general
date: 2026-06-13
surface: agent
model: claude-fable-5
feature: none
branch: main
user: Dua Rizwan
command: chat
labels: ["routing", "intent-detection", "explainer"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - none
tests:
 - none (Q&A follow-up; no code changes)
---

## Prompt

will it now understand the intend and context correctly?

## Response snapshot

Yes for the reported failure modes: ambiguous wording is classified by an LLM router that reads the last 6 conversation turns; short follow-ups resolve from context; residual misroutes self-correct via the silent HANDOFF re-dispatch; mixed requests complete the in-scope part professionally. Stated remaining limits honestly: (1) one platform acts per chat turn — cross-platform action chaining would need an orchestrator-with-tools pattern; (2) routing accuracy tracks the configured LLM provider, with the handoff net covering weaker models; (3) genuinely vague messages route to the general assistant which asks for clarification by design. Suggested verification: restart backend, send platform-flavored queries without naming the platform, inspect agent run steps for direct routes or agent_handoff recovery.

## Outcome

- ✅ Impact: User understands new routing behavior and its boundaries; no code changed.
- 🧪 Tests: n/a
- 📁 Files: none
- 🔁 Next prompts: optional orchestrator-with-tools upgrade for multi-platform actions in one message; live E2E verification.
- 🧠 Reflection: Calibrated confidence — explain both the guarantees (handoff safety net) and the architectural limits (single specialist per turn).

## Evaluation notes (flywheel)

- Failure modes observed: none new.
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): live chat test of cross-platform follow-ups after a Gmail conversation.
