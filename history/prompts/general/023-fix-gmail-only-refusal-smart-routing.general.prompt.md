---
id: 023
title: Fix Gmail-only refusal with smart routing
stage: general
date: 2026-06-13
surface: agent
model: claude-fable-5
feature: none
branch: main
user: Dua Rizwan
command: chat
labels: ["routing", "agents", "orchestrator", "handoff", "intent-detection"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/app/agents/response_format.py
 - backend/app/agents/orchestrator.py
 - backend/app/agents/gmail_agent.py
 - backend/app/agents/calendar_agent.py
 - backend/app/agents/github_agent.py
 - backend/app/agents/slack_agent.py
 - backend/app/agents/jira_agent.py
 - backend/app/agents/dropbox_agent.py
 - backend/app/api/chat.py
 - backend/tests/test_intent_routing_smart.py
 - backend/tests/test_chat_agent_run.py
tests:
 - backend/tests/test_intent_routing_smart.py (new — 9 tests)
 - full backend suite: 106 passed
---

## Prompt

analyze my project fully and see why when i give its query related to other platforms except gmail it sometimes say I only handle Gmail — send a new message and the routing system will get you to the right tool. I dont want this kind of response instead i want it capable to handle query and perform action, understand context smartly, I want full professional response

## Response snapshot

Root cause: (1) keyword-only `detect_intent()` misroutes ambiguous queries (generic Gmail keywords like reply/thread/draft/sent) to the Gmail agent; (2) `gmail_agent.py` system prompt hard-coded the refusal "I only handle Gmail — send a new message…" with no recovery path.

Fix implemented:
1. `detect_intent_smart()` in orchestrator.py — explicit service name → keyword fast-path (only when dominant by margin ≥2) → small LLM classification call with last 6 history turns for context → keyword fallback on any LLM failure.
2. Silent handoff protocol — shared `scope_handoff(platform)` snippet appended to all six specialist prompts; out-of-scope requests emit `HANDOFF:<target>` as the sole output, intercepted before streaming, and chat.py re-dispatches once (recorded as an `agent_handoff` ROUTE step), falling back to the general orchestrator after a second handoff. The user never sees the sentinel.
3. chat.py dispatch chain refactored into a `_SPECIALISTS` table + `dispatch_once()` closure to support re-dispatch; mixed-scope requests now instruct agents to complete their part and mention the rest professionally; refusal phrasing banned in prompts.

## Outcome

- ✅ Impact: Non-Gmail queries no longer get the "I only handle Gmail" dead-end; misroutes self-correct invisibly; routing is context-aware.
- 🧪 Tests: 106 passed (9 new in test_intent_routing_smart.py; one source-slice boundary updated in test_chat_agent_run.py).
- 📁 Files: 9 source files + 2 test files (see frontmatter).
- 🔁 Next prompts: live end-to-end verification with a connected account; consider routing-accuracy telemetry on agent_handoff steps.
- 🧠 Reflection: The "fast and free" keyword router was the architectural bottleneck; a hybrid router plus an agent-level escape hatch fixes both the cause and the symptom.

## Evaluation notes (flywheel)

- Failure modes observed: keyword overlap misrouting; hard-coded refusal trapping users; greedy gmail-first ordering in short-message context fallback.
- Graders run and results (PASS/FAIL): pytest suite PASS (106/106).
- Prompt variant (if applicable): scope_handoff v1 (shared across all six specialists).
- Next experiment (smallest change to try): log detect_intent_smart vs detect_intent disagreement rate to tune the keyword fast-path margin.
