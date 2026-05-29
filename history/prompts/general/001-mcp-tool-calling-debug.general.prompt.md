---
id: "001"
title: MCP Tool Calling Debug Fix
stage: general
date: 2026-05-28
surface: agent
model: claude-sonnet-4-6
feature: none
branch: main
user: dua.rizwan@jonasclub.com
command: chat
labels: ["debugging","mcp","tool-calling","gemini","gmail","calendar"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/chat.py
  - backend/app/agents/gmail_agent.py
  - backend/app/agents/calendar_agent.py
  - backend/app/agents/github_agent.py
tests:
  - manual: MCP subprocess startup verified via debug_mcp.py
  - manual: _sanitize_schema assertions passed
---

## Prompt

please check my projects MCP servers and files where MCP is implemented i have tried using groq api free gemini api but i think the problem is in MCP server files why its not extracting mails and not doing tool calling

## Response snapshot

Systematically debugged MCP server + agent pipeline. Found 3 root causes and applied fixes:

1. **calendar_agent missing `ensure_fresh_token`** in `chat.py` — Calendar tokens expired silently after 1 hour. Gmail had token refresh, Calendar did not. Fixed by adding `ensure_fresh_token(calendar_conn, db)` before `run_calendar_agent`.

2. **`_sanitize_schema` was too shallow and missing `default` field stripping** — Gemini's OpenAI-compat endpoint silently refuses to call tools when schemas contain `title`, `$schema`, or `default` at any nesting level. The original function only stripped one level deep and left `default` in property schemas. Fixed by making the function fully recursive and adding `default` to the strip set in all 3 agents.

3. **`msg.content = None` in tool-call assistant messages** — When Gemini returns a tool call, `msg.content` is `None`. Passing `"content": null` back in subsequent API turns causes some Gemini versions to reject the request. Fixed by using `msg.content or ""` in all 3 agents.

Key diagnostic finding: MCP subprocess itself starts correctly and discovers tools fine. The bug was in the schema sanitization and token refresh logic, not in the MCP server files.

## Outcome

- ✅ Impact: Tool calling should now work for Gmail, Calendar, and GitHub. Calendar tokens now refresh properly.
- 🧪 Tests: Verified _sanitize_schema removes title+default recursively; verified MCP server starts and lists 10 tools.
- 📁 Files: 4 files modified (chat.py, gmail_agent.py, calendar_agent.py, github_agent.py)
- 🔁 Next prompts: Test by sending "show me my emails" and checking tool_call_start events in the SSE stream
- 🧠 Reflection: The `default` field in property schemas was the most likely silent killer — Gemini rejects schemas with it without any error message.

## Evaluation notes (flywheel)

- Failure modes observed: Gemini silently skipping tool calls due to `default` in JSON Schema properties; calendar tokens expiring with no refresh
- Graders run and results (PASS/FAIL): Schema sanitization assertions PASS; MCP subprocess startup PASS
- Prompt variant (if applicable): null
- Next experiment: Add explicit `tool_choice="required"` on first LLM call if tool calling still doesn't trigger reliably
