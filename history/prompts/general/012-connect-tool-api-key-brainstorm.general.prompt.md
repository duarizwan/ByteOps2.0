---
id: "012"
title: Connect Tool API Key Brainstorm
stage: general
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: connect-tool-api-key
branch: 1-agent-runs-graph
user: Dua Rizwan
command: chat
labels: ["brainstorming","ux","modal","api-key","tool-connection","settings"]
links:
  spec: docs/superpowers/specs/2026-06-02-connect-tool-api-key-design.md
  ticket: null
  adr: null
  pr: null
files:
  - docs/superpowers/specs/2026-06-02-connect-tool-api-key-design.md
tests:
  - n/a (design phase)
---

## Prompt

I want when user click on connect new tool a window appears that ask for API key and new platform needed details that are require to connect the app in byteops and there will be an option to see existing tools then show that screen which is currently showing when we click on connect new tool

## Response snapshot

Ran full brainstorming session (superpowers:brainstorming skill). Explored codebase, discussed 3 layout options via visual companion mockups, recommended and got approval for Option A (Tabs). Designed per-tool credential forms for GitHub (PAT), Jira (workspace+email+token), Slack (bot token), Trello (API key+token), Dropbox (access token). Gmail/Calendar remain OAuth-only with dimmed chips. Wrote and committed design spec.

Key decisions:
- Two-tab modal: "API Key" (default) + "OAuth (existing)"
- 5 tools support API key; Gmail/Calendar are OAuth-only
- Backend: new POST /api/auth/{tool}/connect-apikey endpoint with credential validation
- One new DB column: auth_method VARCHAR DEFAULT 'oauth'

## Outcome

- ✅ Impact: Design spec approved, committed to docs/superpowers/specs/
- 🧪 Tests: None yet (design phase)
- 📁 Files: 1 spec file created
- 🔁 Next prompts: writing-plans skill to generate implementation plan
- 🧠 Reflection: Visual companion mockups were very effective for getting quick approval on layout option

## Evaluation notes (flywheel)

- Failure modes observed: Visual companion server needed --foreground + run_in_background workaround on Windows
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment: Pre-check server state before each mockup write to avoid stale server issues
