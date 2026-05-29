---
id: 008
title: Inject RESPONSE_FORMAT into Jira and Dropbox Agents
stage: green
date: 2026-05-29
surface: agent
model: claude-sonnet-4-6
feature: response-format
branch: master
user: dua.rizwan@jonasclub.com
command: implement tasks 7 and 8 of response-format feature
labels: ["response-format","jira","dropbox","agent","system-prompt"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/agents/jira_agent.py
  - backend/app/agents/dropbox_agent.py
tests:
  - tests/test_response_format.py::test_jira_prompt_contains_format_rules
  - tests/test_response_format.py::test_dropbox_prompt_contains_format_rules
  - tests/test_response_format.py (all 13 tests)
---

## Prompt

You are implementing Tasks 7 and 8 of the ByteOps response-format feature. Working directory: `D:\OneDrive - Jonas Software\Dua Stuff\uni\Byteops\ByteOps-master`

**Context:** `backend/app/agents/response_format.py` exists with `RESPONSE_FORMAT`. Tasks 3–6 already updated Gmail, Calendar, GitHub, Slack. Now update Jira and Dropbox, then run the full test suite.

### TASK 7: `backend/app/agents/jira_agent.py`
1. Add import: `from app.agents.response_format import RESPONSE_FORMAT`
2. In `JIRA_SYSTEM_PROMPT`, delete: `- Format responses in clean Markdown tables for issue lists.`
3. Change the closing `"""` to `""" + RESPONSE_FORMAT`

### TASK 8: `backend/app/agents/dropbox_agent.py`
1. Add import: `from app.agents.response_format import RESPONSE_FORMAT`
2. In `DROPBOX_SYSTEM_PROMPT`, replace: `- Format file listings as clean Markdown tables with name, type, size, modified date.` with `- For file listings, use a table with columns: name, type, size, modified date.`
3. Change the closing `"""` to `""" + RESPONSE_FORMAT`

### FINAL: Run all 13 tests: `cd backend && uv run python -m pytest tests/test_response_format.py -v`

## Response snapshot

Both files updated as specified. All 13 tests passed in 2.97s. Commits created:
- `89dc6bc` — feat: inject RESPONSE_FORMAT into Jira agent system prompt
- `34f2259` — feat: inject RESPONSE_FORMAT into Dropbox agent system prompt

## Outcome

- Impact: RESPONSE_FORMAT is now injected into all 6 specialist agents (Gmail, Calendar, GitHub, Slack, Jira, Dropbox) ensuring consistent response formatting rules across all agents.
- Tests: 13/13 PASSED — all response format tests green.
- Files: backend/app/agents/jira_agent.py, backend/app/agents/dropbox_agent.py
- Next prompts: Tasks 9–11 (P2): create tool-capabilities.ts, add help popover, update RESPONSE_FORMAT with help icon mention.
- Reflection: Straightforward injection pattern, consistent with Tasks 3–6. The Dropbox task required a line replacement rather than pure deletion, handled cleanly with Edit tool.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): test_jira_prompt_contains_format_rules PASS, test_dropbox_prompt_contains_format_rules PASS, full suite 13/13 PASS
- Prompt variant (if applicable): null
- Next experiment (smallest change to try): null
