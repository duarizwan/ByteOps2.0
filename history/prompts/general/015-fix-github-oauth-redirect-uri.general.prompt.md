---
id: "015"
title: Fix GitHub OAuth redirect URI
stage: general
date: 2026-06-11
surface: agent
model: claude-4.6-sonnet-medium-thinking
feature: none
branch: unknown
user: rizwadua
command: null
labels: ["github", "oauth", "redirect-uri", "troubleshooting"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
 - backend/app/core/config.py
 - backend/app/api/oauth.py
 - backend/.env
tests:
 - none
---

## Prompt

when i am connecting github it shows me this

[GitHub error: The redirect_uri is not associated with this application.]

## Response snapshot

Diagnosed OAuth redirect_uri mismatch: ByteOps sends `http://localhost:8000/api/auth/github/callback` (from GITHUB_REDIRECT_URI). User must add that exact URL to their GitHub OAuth App Authorization callback URL, or connect via the API Key tab with a Personal Access Token instead.

## Outcome

- ✅ Impact: Explained root cause and fix steps; no code changes required
- 🧪 Tests: none
- 📁 Files: inspected oauth.py, config.py, .env
- 🔁 Next prompts: Confirm GitHub OAuth app callback URL updated; retry connect
- 🧠 Reflection: Common local-dev OAuth misconfiguration; API key path is simpler for GitHub

## Evaluation notes (flywheel)

- Failure modes observed: GitHub OAuth app missing or mismatched callback URL
- Graders run and results (PASS/FAIL): n/a
- Prompt variant (if applicable): n/a
- Next experiment (smallest change to try): n/a
