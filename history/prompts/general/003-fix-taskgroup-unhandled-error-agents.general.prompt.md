---
id: "003"
title: Fix TaskGroup Unhandled Error in Calendar and GitHub Agents
stage: general
date: 2026-05-28
surface: agent
model: claude-sonnet-4-6
feature: none
branch: unknown
user: dua.rizwan@jonasclub.com
command: "still showing this error ⚠️ unhandled errors in a TaskGroup (1 sub-exception)"
labels: ["debugging","asyncio","anyio","mcp","taskgroup","exception-handling"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/agents/calendar_agent.py
  - backend/app/agents/github_agent.py
tests:
  - none
---

## Prompt

still showing this error ⚠️ unhandled errors in a TaskGroup (1 sub-exception)

## Response snapshot

Root cause identified: `calendar_agent.py` and `github_agent.py` were missing the `try: ... except BaseExceptionGroup as eg:` wrapper that `gmail_agent.py` already had around its `async with stdio_client(...)` block.

When anyio's internal TaskGroup raises `BaseExceptionGroup("unhandled errors in a TaskGroup", ...)` on MCP subprocess exit, it propagates to `chat.py`'s `except Exception as exc:` — which cannot catch it because `BaseExceptionGroup` inherits from `BaseException`, not `Exception`. The exception escaped to the asyncio event loop, producing the warning.

Fix applied to both `calendar_agent.py` and `github_agent.py`: wrapped the entire `async with stdio_client(...)` block in `try: ... except BaseExceptionGroup as eg:` identical to the pattern in `gmail_agent.py`, converting the grouped exception to a plain `RuntimeError` that `chat.py`'s handler can catch.

## Outcome

- ✅ Impact: The TaskGroup warning is eliminated for Calendar and GitHub agent calls; errors are now surfaced as clean RuntimeErrors to the SSE error stream
- 🧪 Tests: No automated tests run; fix mirrors proven pattern from gmail_agent.py
- 📁 Files: calendar_agent.py lines 113-204, github_agent.py lines 84-157
- 🔁 Next prompts: Test Calendar and GitHub agent calls end-to-end to confirm error messages surface correctly in UI
- 🧠 Reflection: Pattern inconsistency across three near-identical agent files — worth enforcing via a shared helper or base class in future

## Evaluation notes (flywheel)

- Failure modes observed: Missing exception handler in two of three identical agent files — copy-paste divergence
- Graders run and results (PASS/FAIL): none
- Prompt variant (if applicable): none
- Next experiment (smallest change to try): Extract shared MCP client context logic into a single helper to prevent future divergence
