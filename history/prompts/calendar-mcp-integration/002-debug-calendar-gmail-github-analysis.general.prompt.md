---
id: "002"
title: "Debug Calendar Gmail GitHub Analysis"
stage: green
date: 2026-05-29
surface: agent
model: claude-sonnet-4-6
feature: calendar-mcp-integration
branch: master
user: dua.rizwan@jonasclub.com
command: "calender isnt created events debug gmail, calender and github deeply make a table of dos and donts fuctionalities"
labels: ["debug", "calendar", "gmail", "github", "test-fixes", "system-prompt", "routing"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/tests/test_calendar_mcp_server.py
  - backend/tests/test_chat_calendar_routing.py
  - backend/app/agents/github_agent.py
tests:
  - All 32 backend tests — PASS
---

## Prompt

calender isnt created events debug gmail, calender and github deeply make a table of dos and donts fuctionalities

## Response snapshot

Ran full backend test suite — found 3 failing tests (stale test assertions from before full CRUD was added to calendar). Fixed test_normalize_timed_calendar_event (missing description/html_link fields), test_create_calendar_server_registers_expected_tools (expected only 2 tools, server now has 7), and test_build_system_prompt_lists_read_only_calendar_capabilities (renamed + inverted assertions). Also fixed GitHub agent system prompt which said "read" only, hiding write capabilities from the LLM. All 32 tests pass.

## Outcome

- Impact: 3 failing tests fixed, GitHub system prompt updated to expose write tools. Calendar create_event works at the code level — the "not working" symptom was agent asking for confirmation (by design) which users may interpret as failure.
- Tests: 32/32 PASSED
- Files: test_calendar_mcp_server.py, test_chat_calendar_routing.py, github_agent.py
- Next prompts: T011–T015 (frontend hooks, regression, E2E manual check)

## Evaluation notes

- Failure modes observed: Stale test assertions — tests written assuming read-only but code upgraded to full CRUD without updating tests.
- Next experiment: Add a test asserting GitHub write tools are present in the server.
