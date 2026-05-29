---
id: "009"
title: "Fix Slack PKCE and Jira Redirect OAuth Errors"
stage: green
date: 2026-05-29
surface: agent
model: claude-sonnet-4-6
feature: none
branch: master
user: dua.rizwan@jonasclub.com
command: "Hmm... We're having trouble logging you in. (JIRA) Must use PKCE to redirect to a non-web URI (slack)"
labels: ["oauth", "pkce", "slack", "jira", "auth", "bug-fix"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/oauth.py
tests:
  - tests/test_oauth.py (7/7 PASS)
---

## Prompt

Hmm... We're having trouble logging you in. The app's callback URL is invalid. (JIRA)
Must use PKCE to redirect to a non-web URI (slack)

## Response snapshot

Diagnosed two distinct OAuth errors. Slack: implemented PKCE (S256) in oauth.py — added _pkce_pair(), _pkce_save(), _pkce_pop() helpers plus an in-process nonce store, injected code_challenge into Slack's initiate URL, captured state_nonce in callback, added code_verifier to Slack token exchange. Jira: config-only fix — user must add the redirect URI to their Atlassian app settings. All 7 OAuth tests pass.

## Outcome

- Impact: Slack OAuth will now complete without PKCE error. Jira OAuth requires one developer dashboard config step.
- Tests: 7/7 PASS
- Files: backend/app/api/oauth.py
- Next prompts: Test Slack and Jira connections end-to-end; add Jira + Dropbox token refresh to token_refresh.py
