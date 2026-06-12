---
id: "013"
title: Backend connect-apikey endpoint
stage: green
date: 2026-06-02
surface: agent
model: claude-sonnet-4-6
feature: api-key-auth
branch: 1-agent-runs-graph
user: dua.rizwan@jonasclub.com
command: implement Task 1 Backend connect-apikey endpoint
labels: ["backend","oauth","api-key","tdd","fastapi"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files:
  - backend/app/api/oauth.py
  - backend/tests/test_oauth.py
tests:
  - tests/test_oauth.py::test_connect_apikey_github_valid
  - tests/test_oauth.py::test_connect_apikey_github_invalid_token
  - tests/test_oauth.py::test_connect_apikey_gmail_rejected
  - tests/test_oauth.py::test_connect_apikey_jira_missing_fields
---

## Prompt

Implement Task 1: Backend — connect-apikey endpoint. Write tests first (TDD), make them fail, implement, make them pass, commit. Add POST /{tool}/connect-apikey endpoint to backend/app/api/oauth.py that validates API key credentials with a live test call and stores them in ToolConnection. Supported tools: GitHub, Jira, Slack, Trello, Dropbox. Gmail and Calendar must be rejected with 400.

## Response snapshot

- Added 4 failing tests to backend/tests/test_oauth.py using app.dependency_overrides pattern (consistent with existing tests, not the patch(return_value=...) pattern from the spec which doesn't work with FastAPI Depends)
- Confirmed 4 FAILED (404 Not Found — endpoint missing)
- Added `from pydantic import BaseModel` import and `ApiKeyCredentials` model to oauth.py
- Added module-level `from app.services.sync.scheduler import trigger_immediate_sync` so the name is patchable
- Added `_APIKEY_SUPPORTED` set, `_validate_apikey_credentials()`, `_extract_token_and_metadata()`, and `connect_tool_apikey()` route before disconnect_tool
- 4/4 new tests PASS, 11/11 total oauth tests PASS (zero regressions)
- Committed as feat: add connect-apikey endpoint for GitHub, Jira, Slack, Trello, Dropbox

## Outcome

- Impact: New POST /api/auth/{tool}/connect-apikey endpoint live for GitHub, Jira, Slack, Trello, Dropbox. Gmail/Calendar correctly rejected with 400 "does not support API key auth. Use OAuth."
- Tests: 4 new tests added; 11/11 pass
- Files: backend/app/api/oauth.py (endpoint + helpers), backend/tests/test_oauth.py (4 new tests)
- Next prompts: Task 2 (hook connectViaApiKey), Task 3 (frontend modal), Task 4 (fix mocks)
- Reflection: Task spec used patch(return_value=...) for FastAPI deps which doesn't work — adapted to app.dependency_overrides pattern matching codebase conventions

## Evaluation notes (flywheel)

- Failure modes observed: patch(return_value=...) on FastAPI Depends functions doesn't intercept — must use app.dependency_overrides; trigger_immediate_sync local import not patchable at module level — moved to module-level import
- Graders run and results (PASS/FAIL): uv run python -m pytest tests/test_oauth.py -v → 11 PASSED
- Prompt variant (if applicable): null
- Next experiment: null
