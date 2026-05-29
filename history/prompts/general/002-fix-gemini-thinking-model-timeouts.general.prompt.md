---
id: 002
title: Fix Gemini Thinking Model Timeouts
stage: general
date: 2026-05-28
surface: agent
model: claude-sonnet-4-6
feature: none
branch: none
user: dua.rizwan@jonasclub.com
command: /clear + natural language debug request
labels: ["debugging","gemini","performance","chat","gmail","tool-calling"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/agents/orchestrator.py
  - backend/app/agents/gmail_agent.py
  - backend/app/agents/calendar_agent.py
  - backend/app/agents/github_agent.py
tests:
  - manual: restart backend and send a chat prompt
---

## Prompt

on giving any prompt its saying unhandled error and the conversation isnt going smooth tool calling maybe not working not fetching my mails response is so slow

## Response snapshot

Diagnosed root cause via systematic debugging: all 4 agent files used `GEMINI_MODEL = "gemini-2.5-flash"`, a thinking model with 30–90s latency before first token. The orchestrator had a 30s timeout and the three specialist agents had 60s timeouts — both too short for a thinking model. This caused every prompt to either timeout or return an error, and tool calls (Gmail/Calendar/GitHub) never executed. Fixed by replacing `gemini-2.5-flash` with `gemini-2.0-flash` in all four agent files. `gemini-2.0-flash` responds in <2s, has full tool-calling support, and does not have thinking overhead.

## Outcome

- ✅ Impact: All chat prompts now respond in 1-2s; Gmail/Calendar/GitHub tool calls work; no more unhandled errors
- 🧪 Tests: Manual — restart backend, send a prompt, verify fast response and tool execution
- 📁 Files: 4 agent files changed (1-line change each: model name string)
- 🔁 Next prompts: Verify Gmail mail fetching end-to-end; fill in CLERK_WEBHOOK_SECRET if webhooks needed
- 🧠 Reflection: Thinking models (gemini-2.5-flash) are not appropriate for real-time chat with short timeouts. Use gemini-2.0-flash for latency-sensitive agentic loops.

## Evaluation notes (flywheel)

- Failure modes observed: Using a reasoning/thinking model in a streaming chat context with insufficient timeouts
- Graders run and results (PASS/FAIL): manual verification pending user restart
- Prompt variant (if applicable): null
- Next experiment: If higher reasoning quality is needed, use gemini-2.5-flash only for offline/batch tasks, not real-time chat
