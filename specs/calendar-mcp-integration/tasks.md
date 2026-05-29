# Tasks: Calendar MCP Integration

**Input**: `specs/calendar-mcp-integration/spec.md`, `specs/calendar-mcp-integration/plan.md`  
**Prerequisites**: Approved spec and plan  
**Execution Mode**: Test-first, smallest viable diffs, no unrelated UI redesign

## Phase 1: OAuth and Configuration Baseline

- [x] **T001 - Add Calendar OAuth tests**
  - Files: `backend/tests/test_oauth.py`
  - Add or extend tests for `GET /api/auth/calendar/initiate`.
  - Acceptance: Missing Calendar credentials returns 501, and configured credentials return an auth URL containing Google Calendar scope.
  - Run: `cd backend; uv run pytest tests/test_oauth.py -v`

- [x] **T002 - Verify Calendar OAuth provider configuration**
  - Files: `backend/app/api/oauth.py`, `.env.example`
  - Ensure Calendar scopes include read access for event listing and callback paths match the actual backend route `/api/auth/calendar/callback`.
  - Acceptance: The OAuth tests from T001 pass and `.env.example` no longer points Calendar callbacks at a nonexistent `/api/tools/...` path.
  - Run: `cd backend; uv run pytest tests/test_oauth.py -v`

## Phase 2: Calendar MCP Server

- [x] **T003 - Write Calendar MCP server normalization tests**
  - Files: `backend/tests/test_calendar_mcp_server.py`
  - Test that a raw Google Calendar event with `dateTime` becomes a normalized summary with title, start, end, attendees, meeting link, and status.
  - Test that an all-day event with `date` is normalized without crashing.
  - Acceptance: Tests fail before `backend/app/mcp_servers/calendar/server.py` exists.
  - Run: `cd backend; uv run pytest tests/test_calendar_mcp_server.py -v`

- [x] **T004 - Implement Calendar MCP package**
  - Files: `backend/app/mcp_servers/calendar/__init__.py`, `backend/app/mcp_servers/calendar/server.py`
  - Implement `CalendarClient`, `create_calendar_server()`, `list_events`, and `search_events`.
  - Use env vars `CALENDAR_ACCESS_TOKEN`, `CALENDAR_REFRESH_TOKEN`, `CALENDAR_CLIENT_ID`, and `CALENDAR_CLIENT_SECRET`.
  - Acceptance: T003 tests pass.
  - Run: `cd backend; uv run pytest tests/test_calendar_mcp_server.py -v`

- [x] **T005 - Add Calendar MCP entrypoint smoke test**
  - Files: `backend/tests/test_calendar_mcp_server.py`
  - Test that `create_calendar_server()` registers expected tool names when the client is patched.
  - Acceptance: The MCP server exposes `list_events` and `search_events`.
  - Run: `cd backend; uv run pytest tests/test_calendar_mcp_server.py -v`

## Phase 3: Calendar Agent and Routing

- [x] **T006 - Write orchestrator Calendar intent tests**
  - Files: `backend/tests/test_chat_calendar_routing.py`, `backend/app/agents/orchestrator.py`
  - Test that prompts like "What's on my calendar today?" and "Find meetings this week" return `calendar`.
  - Acceptance: Tests pass with existing or refined keyword detection.
  - Run: `cd backend; uv run pytest tests/test_chat_calendar_routing.py -v`

- [x] **T007 - Add Calendar tool capability descriptions**
  - Files: `backend/app/agents/orchestrator.py`
  - Ensure `build_system_prompt()` accurately lists Calendar read capabilities when Calendar is connected.
  - Acceptance: Prompt-building test verifies Calendar tools are listed only when connected.
  - Run: `cd backend; uv run pytest tests/test_chat_calendar_routing.py -v`

- [x] **T008 - Write Calendar agent environment and streaming tests**
  - Files: `backend/tests/test_calendar_agent.py`
  - Patch stdio MCP and LLM dependencies to verify the agent passes Calendar tokens to the subprocess and emits tool-call events.
  - Acceptance: Tests fail until `run_calendar_agent()` exists.
  - Run: `cd backend; uv run pytest tests/test_calendar_agent.py -v`

- [x] **T009 - Implement Calendar specialist agent**
  - Files: `backend/app/agents/calendar_agent.py`
  - Mirror the Gmail agent structure with Calendar-specific env vars, system prompt, MCP tool discovery, tool execution, and SSE queue events.
  - Acceptance: T008 tests pass.
  - Run: `cd backend; uv run pytest tests/test_calendar_agent.py -v`

- [x] **T010 - Route Calendar chat requests**
  - Files: `backend/app/api/chat.py`
  - Import `run_calendar_agent`; when intent is `calendar`, find `ToolType.CALENDAR`; if missing, stream a Settings guidance message.
  - Acceptance: Connected Calendar calls the Calendar agent; disconnected Calendar returns guidance.
  - Run: `cd backend; uv run pytest tests/test_chat_calendar_routing.py -v`

## Phase 4: UI Connection Reliability

- [ ] **T011 - Add frontend connection hook tests**
  - Files: `frontend/tests/tool-connections.test.tsx`, `frontend/src/hooks/use-tool-connections.ts`
  - Test that `initiateConnect("calendar")` calls `/api/auth/calendar/initiate` and surfaces backend error details.
  - Acceptance: Tests pass without changing the public hook API.
  - Run: `cd frontend; npm run test:run -- tool-connections.test.tsx`

- [ ] **T012 - Verify Calendar Settings card behavior**
  - Files: `frontend/src/app/settings/page.tsx`, `frontend/src/components/dashboard/tool-card.tsx`
  - Ensure Calendar uses the existing ToolCard flow, shows loading/error states, and does not claim success on failed initiation.
  - Acceptance: Manual Settings page check can connect, reconnect, and disconnect Calendar with clear errors.
  - Run: `cd frontend; npm run test:run`

## Phase 5: Regression and Manual Verification

- [ ] **T013 - Run backend regression tests**
  - Files: backend test suite
  - Acceptance: Existing Gmail/OAuth/chat tests still pass.
  - Run: `cd backend; uv run pytest -v`

- [ ] **T014 - Run frontend regression tests and lint**
  - Files: frontend test suite
  - Acceptance: Frontend tests and lint complete without Calendar-related failures.
  - Run: `cd frontend; npm run test:run`
  - Run: `cd frontend; npm run lint`

- [ ] **T015 - Manual end-to-end Calendar read check**
  - Files: `.env`, browser, backend logs
  - Configure Calendar OAuth credentials, start backend and frontend, connect Calendar, and ask "What's on my calendar today?"
  - Acceptance: Chat streams a Calendar MCP tool call and returns real event data from the connected account.

## Out of Scope for This Task List

- Slack, GitHub, JIRA, and Dropbox integrations.
- Full UI redesign or shadcn/ui migration.
- Background Calendar notification sync.
- Executing Calendar create/update/delete operations after confirmation.
