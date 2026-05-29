---
id: 006
title: Fix Activity Pane Routing
stage: general
date: 2026-05-29
surface: agent
model: GPT-5 Codex
feature: none
branch: none
user: rizwadua
command: fix activity pane routing
labels: ["frontend","activity-pane","notifications","tasks"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - history/prompts/general/006-fix-activity-pane-routing.general.prompt.md
tests:
  - not run yet; implementation gated on design approval
---

## Prompt

 fix activity pane it seems like everything is appearing in alert pane
  and do not show user query in alert instead show something which needs
  attention or that is being extracted and is imp to user then set its
  priority and if some extracted thing from gmail slack or any platform
  indicates some tasks to beperformed by user show/list them in the tasks

## Response snapshot

Investigated the right-panel activity feed and notification creation path. Found that the frontend Alerts tab currently renders all notifications, while the Tasks tab only accepts Jira, Trello, and GitHub source tools. The chat notification persistence also stores the raw user query as the notification title, which explains why prompts appear in Alerts instead of extracted attention items.

## Outcome

- ✅ Impact: Root cause identified; ready to implement a small classification and rendering fix after approval.
- 🧪 Tests: not run yet; proposed next step is frontend red test before implementation.
- 📁 Files: created this PHR only.
- 🔁 Next prompts: approve the proposed design, then implement and verify the activity pane fix.
- 🧠 Reflection: Keep the API shape stable and classify existing notification records defensively in the UI while improving new chat-created notifications at the source.

## Evaluation notes (flywheel)

- Failure modes observed: Alerts bucket accepts every notification; task bucket excludes Gmail and Slack action items; chat-created notifications use user query as title.
- Graders run and results (PASS/FAIL): none yet.
- Prompt variant (if applicable): null.
- Next experiment (smallest change to try): add failing ContextPanel tests for alert/task classification, then implement helper-based filtering and improve chat notification title/content metadata.
