---
id: 008
title: Clean Activity Pane Characters
stage: general
date: 2026-05-29
surface: agent
model: GPT-5 Codex
feature: none
branch: none
user: rizwadua
command: do not show special characters like * - | in tasks alert or workflows
labels: ["frontend","backend","activity-pane","text-sanitization"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - frontend/src/components/dashboard/context-panel.tsx
  - frontend/tests/context-panel.test.tsx
  - backend/app/api/chat.py
  - backend/tests/test_chat_activity_notification.py
  - history/prompts/general/008-clean-activity-pane-characters.general.prompt.md
tests:
  - npm run test:run -- tests/context-panel.test.tsx
  - backend/.venv/Scripts/python.exe -m pytest tests/test_chat_activity_notification.py
---

## Prompt

do not show special characters like * - | in tasks alert or workflows

## Response snapshot

Added focused sanitization so activity pane cards display clean text without markdown, list, or table marker characters. Frontend task and alert cards now clean visible titles and content. Backend chat-created activity payloads now clean extracted title and content before persistence, so new alerts and tasks avoid those characters at the source.

## Outcome

- ✅ Impact: Tasks and alerts no longer display `*`, `-`, or `|` marker characters in notification card titles or content.
- 🧪 Tests: focused frontend ContextPanel tests pass; focused backend activity notification tests pass.
- 📁 Files: updated ContextPanel, ContextPanel tests, chat activity payload helper, backend payload tests, and this PHR.
- 🔁 Next prompts: apply the same sanitizer to future workflow cards when workflow records are implemented.
- 🧠 Reflection: Display-level sanitization covers existing stored records while backend sanitization keeps new extracted activity cleaner.

## Evaluation notes (flywheel)

- Failure modes observed: Markdown and table marker characters were displayed directly from notification title/content.
- Graders run and results (PASS/FAIL): focused frontend PASS; focused backend PASS.
- Prompt variant (if applicable): null.
- Next experiment (smallest change to try): add workflow-card tests once workflow activity data exists.
