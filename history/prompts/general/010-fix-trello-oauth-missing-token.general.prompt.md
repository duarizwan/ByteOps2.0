---
id: 010
title: Fix Trello OAuth missing token error
stage: general
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: none
branch: 1-agent-runs-graph
user: Dua Rizwan
command: chat
labels: ["oauth", "trello", "debugging", "bug-fix"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/oauth.py
  - .env.example
tests:
  - none
---

## Prompt

when i am hitting connect btn of trello it redirect me to another page and asking "Allow" after allowing it again bring me back to my app but showing this error OAuth2 error: trello_missing_token what is the possible reason and what to do in it

## Response snapshot

Root cause identified: the `return_url` passed to Trello's authorize endpoint already contained a `?nonce=...` query parameter. When Trello redirects back after the user clicks "Allow", it appends `?token=TOKEN` literally — producing a malformed double-`?` URL like `...?nonce=abc?token=TOKEN`. Python's URL parser treats everything after the first `?` as one query string, so `token` is never seen as a separate parameter and remains `None`, triggering the `trello_missing_token` error.

Fix: moved the nonce from a query parameter to a path segment in the `return_url` (`/callback/{nonce}`) and added a dedicated `GET /trello/callback/{nonce}` route. Trello now appends `?token=TOKEN` to a clean URL, which FastAPI parses correctly.

## Outcome

- ✅ Impact: Trello OAuth connect flow completes without error
- 🧪 Tests: manual end-to-end test needed after backend restart
- 📁 Files: backend/app/api/oauth.py refactored; .env.example annotated
- 🔁 Next prompts: test the flow manually; consider in-memory nonce store limitation for multi-worker deploys
- 🧠 Reflection: Trello's non-standard token-in-redirect behavior requires nonce-in-path instead of nonce-in-query

## Evaluation notes (flywheel)

- Failure modes observed: double-? URL from Trello appending ?token= to already-querystring URL
- Graders run and results (PASS/FAIL): none automated
- Prompt variant (if applicable): none
- Next experiment: add integration test that simulates the Trello redirect callback
