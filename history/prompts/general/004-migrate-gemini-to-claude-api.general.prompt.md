---
id: "004"
title: Migrate Gemini to Claude API
stage: general
date: 2026-05-28
surface: agent
model: claude-sonnet-4-6
feature: none
branch: main
user: dua.rizwan@jonasclub.com
command: chat
labels: ["migration", "claude-api", "agents", "gmail", "chat"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/pyproject.toml
  - backend/app/core/config.py
  - backend/app/agents/orchestrator.py
  - backend/app/agents/gmail_agent.py
  - backend/app/agents/calendar_agent.py
  - backend/app/agents/github_agent.py
  - backend/app/api/chat.py
tests:
  - manual: python import verification — all agents import cleanly with claude_api_key loaded
---

## Prompt

now I have replaced my gemini api key with claude api key analyze the code according to that do let me know if any fixes required and now i want my chats will work and emails will be fetched

## Response snapshot

Analyzed the full codebase. Found 6 files that needed updating for the Gemini → Claude API migration:

1. `pyproject.toml` — added `anthropic>=0.44.0` dependency; installed via `uv add anthropic` (got v0.105.0)
2. `config.py` — renamed `gemini_api_key` → `claude_api_key` to match the `.env` variable `CLAUDE_API_KEY`
3. `orchestrator.py` — replaced `AsyncOpenAI` + Gemini endpoint with `anthropic.AsyncAnthropic`; updated streaming to use `client.messages.stream()` with `stream.text_stream`; model changed to `claude-sonnet-4-6`
4. `gmail_agent.py` — replaced OpenAI tool-call format (`parameters`, `choices[0].message.tool_calls`) with Anthropic format (`input_schema`, `response.content` blocks, `tool_use`/`tool_result` message structure)
5. `calendar_agent.py` — same changes as gmail_agent
6. `github_agent.py` — same changes as gmail_agent
7. `chat.py` — updated rate-limit error message (removed Gemini-specific text)

Key API format differences handled:
- System prompt moved from a message role to a separate `system=` parameter
- Tools use `input_schema` instead of `parameters`; no schema sanitization needed
- Response content is a list of typed blocks (`TextBlock`, `ToolUseBlock`) instead of `choices[0].message`
- Tool results go back as `user` messages with `tool_result` content blocks (not `tool` role messages)
- Streaming uses `async with client.messages.stream() as stream: async for text in stream.text_stream`

## Outcome

- ✅ Impact: All chats and email fetching now use Claude API; Gemini dependency fully removed from agent code
- 🧪 Tests: Import verification passed — `claude_api_key set: True`, all agent imports OK
- 📁 Files: 7 files modified
- 🔁 Next prompts: Test a live chat message; test Gmail fetch; verify streaming appears in frontend
- 🧠 Reflection: Migration was straightforward because the OpenAI-compat wrapper was already abstracting the protocol; main work was adapting the tool-call loop to Anthropic's content-block format

## Evaluation notes (flywheel)

- Failure modes observed: none during import verification
- Graders run and results (PASS/FAIL): import test PASS
- Prompt variant (if applicable): null
- Next experiment: run backend and send a test message to confirm end-to-end streaming
