---
id: 007
title: Response Format and Help Center Planning
stage: plan
date: 2026-05-29
surface: agent
model: claude-sonnet-4-6
feature: none
branch: main
user: dua.rizwan@jonasclub.com
command: brainstorm + writing-plans
labels: ["response-format","help-center","planning","ux"]
links:
  spec: docs/superpowers/specs/2026-05-29-response-format-design.md
  ticket: null
  adr: null
  pr: null
files:
  - docs/superpowers/specs/2026-05-29-response-format-design.md
  - docs/superpowers/specs/2026-05-29-help-center-design.md
  - docs/superpowers/plans/2026-05-29-response-format.md
  - docs/superpowers/plans/2026-05-29-help-center.md
tests:
  - backend/tests/test_response_format.py (planned)
  - frontend/tests/tool-capabilities.test.ts (planned)
  - frontend/tests/chat-interface.test.tsx (extensions planned)
---

## Prompt

1) improve the response format — byteops response contains lots of "--" | * and special characters which seems like too much AI-centered and unattractive — maybe make a skill or md file of clean organized and structured response format accordingly

2) use ? icon somewhere which means help that tells the capability or what functionalities user can perform in each platform and if user asks something that is out of scope then chat could refer that help center to the user but not every time

## Response snapshot

Brainstormed both features through clarifying questions. User chose:
- Feature 1: Plain conversational prose via a shared RESPONSE_FORMAT constant (Approach 1 — single source of truth injected into all 7 agent system prompts).
- Feature 2: One global ? icon in the chat header opening a tooltip/popover with per-connected-tool capability lists. AI nudge handled purely via system prompt — no extra UI.

Produced two design docs and two full TDD implementation plans with complete code, exact file paths, and precise test commands.

## Outcome

- ✅ Impact: Two complete implementation plans ready for execution — backend prose format fix and frontend help center feature.
- 🧪 Tests: 13 backend pytest tests (response-format plan) + 5 frontend source-level tests for capabilities + 8 new chat-interface source checks (help-center plan).
- 📁 Files: 4 new docs created (2 specs, 2 plans). No code changed yet.
- 🔁 Next prompts: Execute plans using subagent-driven-development or executing-plans skill. Run response-format plan first (prerequisite for help-center).
- 🧠 Reflection: Source-level frontend test pattern (read file, assert on text) correctly followed to match existing test style and avoid react-markdown ESM memory issues.

## Evaluation notes (flywheel)

- Failure modes observed: none
- Graders run and results (PASS/FAIL): n/a — planning session only
- Prompt variant (if applicable): n/a
- Next experiment: execute plans and verify AI chat responses no longer contain decorative markdown
