# Implementation Plan: Calendar MCP Integration

**Branch**: `calendar-mcp-integration` | **Date**: 2026-05-26 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/calendar-mcp-integration/spec.md`

## Summary

Add Google Calendar as the first non-Gmail ByteOps integration using the existing OAuth, chat, and MCP patterns. The first slice is read-first: users can connect Calendar, ask schedule questions, and receive event summaries through a Calendar MCP subprocess and specialist agent. Calendar write/delete requests must stop at a confirmation proposal and must not mutate provider data in this slice.

## Technical Context

**Language/Version**: Python 3.12+, TypeScript with React 19 and Next.js 16  
**Primary Dependencies**: FastAPI, SQLAlchemy async, MCP Python SDK, Google API Python Client, OpenAI-compatible Gemini client, Clerk, Next.js App Router  
**Storage**: PostgreSQL via existing `ToolConnection`, `Conversation`, and `Message` models  
**Testing**: `pytest`, `pytest-asyncio`, `Vitest`, React Testing Library  
**Target Platform**: Local FastAPI backend and Next.js frontend; later deployable to Railway/Render and Vercel  
**Project Type**: Web application monorepo with `backend/` and `frontend/`  
**Performance Goals**: Calendar chat responses stream first visible progress within 3 seconds for normal event queries  
**Constraints**: Calendar AI operations must use MCP; credentials must come from `.env`; no unrelated UI modernization; Gmail behavior must remain intact  
**Scale/Scope**: One provider integration, one MCP server, one specialist agent, read-only event tools, one UI callback-path fix if required for connection testing

## Constitution Check

| Principle | Status | Evidence |
|---|---|---|
| AI-First Middleware | Pass | User-facing event queries flow through chat and MCP tools |
| Multi-Agent Architecture | Pass | Calendar specialist follows Gmail agent pattern |
| Three-Panel Dashboard | Pass | Settings status and chat surface stay within existing UI |
| Test-First Development | Pass | Tasks begin with failing pytest/Vitest coverage |
| Security by Design | Pass | Uses per-user OAuth tokens and no hardcoded secrets |
| Production-Grade Quality | Pass | Adds error paths for missing credentials, disconnected tools, token expiry, and MCP failures |

## Project Structure

### Documentation

```text
specs/calendar-mcp-integration/
|-- spec.md
|-- plan.md
`-- tasks.md
```

### Backend Source

```text
backend/
|-- app/
|   |-- agents/
|   |   |-- calendar_agent.py
|   |   |-- gmail_agent.py
|   |   `-- orchestrator.py
|   |-- api/
|   |   |-- chat.py
|   |   `-- oauth.py
|   |-- core/
|   |   `-- config.py
|   |-- mcp_servers/
|   |   |-- calendar/
|   |   |   |-- __init__.py
|   |   |   `-- server.py
|   |   `-- gmail/
|   |       `-- server.py
|   `-- models/
|       `-- tool_connection.py
`-- tests/
    |-- test_calendar_agent.py
    |-- test_calendar_mcp_server.py
    |-- test_chat_calendar_routing.py
    `-- test_oauth.py
```

### Frontend Source

```text
frontend/
|-- src/
|   |-- app/settings/page.tsx
|   `-- hooks/use-tool-connections.ts
`-- tests/
    `-- tool-connections.test.tsx
```

**Structure Decision**: Follow the existing Gmail implementation shape. Calendar gets its own MCP server package and agent file, while shared routing remains in the existing orchestrator and chat API.

## Implementation Approach

### Unit Boundaries

- `backend/app/mcp_servers/calendar/server.py`: Owns Google Calendar API access and exposes MCP tools only.
- `backend/app/agents/calendar_agent.py`: Owns LLM tool-calling loop for Calendar and never calls Google APIs directly.
- `backend/app/agents/orchestrator.py`: Owns intent detection and tool capability descriptions.
- `backend/app/api/chat.py`: Owns selecting the connected Calendar ToolConnection and streaming SSE events.
- `backend/app/api/oauth.py`: Owns provider OAuth initiation and callback; Calendar already exists but callback paths and scopes must be verified.
- `frontend/src/hooks/use-tool-connections.ts`: Owns client-side connect/disconnect calls and error handling.

### Calendar MCP Tools

`list_events` accepts:

```json
{
  "time_min": "2026-05-26T00:00:00+05:00",
  "time_max": "2026-05-27T00:00:00+05:00",
  "calendar_id": "primary",
  "max_results": 10
}
```

It returns:

```json
[
  {
    "id": "event-id",
    "calendar_id": "primary",
    "calendar_name": "Primary",
    "title": "Project sync",
    "start": "2026-05-26T10:00:00+05:00",
    "end": "2026-05-26T10:30:00+05:00",
    "location": "",
    "meeting_link": "https://meet.google.com/example",
    "attendees": ["duarizwan098@gmail.com"],
    "status": "confirmed"
  }
]
```

`search_events` accepts the same time range plus `query`.

### Data Flow

1. User connects Calendar from Settings.
2. Backend OAuth callback stores `ToolConnection(tool_type=calendar)`.
3. User asks a calendar question in chat.
4. `detect_intent()` returns `calendar`.
5. `chat.py` finds the current user's connected Calendar ToolConnection.
6. `calendar_agent.py` starts `python -m app.mcp_servers.calendar.server` with Calendar tokens in environment variables.
7. The agent discovers MCP tools, lets Gemini choose `list_events` or `search_events`, executes the MCP tool, streams tool events, and returns a final answer.
8. `chat.py` persists the assistant response and emits the final SSE `done` event.

### Error Handling

- Missing Calendar connection: return a concise Settings guidance message and persist it.
- Missing OAuth credentials: connect initiation returns 501 with a clear detail string.
- Token expired: Calendar MCP server refreshes via Google credentials when possible; unrecoverable expiry becomes a clear reconnect message.
- MCP server startup failure: chat streams an error event and does not corrupt conversation state.
- Provider permission/rate limit: agent explains the provider error and suggests reconnecting or retrying later.

### Testing Strategy

- MCP server tests patch Google API client construction and verify normalized tool output.
- Calendar agent tests patch MCP session and LLM calls where possible, focusing on environment construction and event streaming.
- Chat routing tests patch `run_calendar_agent` to verify connected/disconnected behavior.
- OAuth tests cover Calendar initiate paths and missing credentials.
- Frontend tests cover connection initiation failure handling and Calendar status display if component-level coverage is practical.

## Acceptance Checks

- [ ] Calendar OAuth initiate endpoint returns a Google consent URL when credentials exist.
- [ ] Calendar OAuth initiate endpoint returns 501 when credentials are missing.
- [ ] Calendar MCP `list_events` normalizes timed and all-day events.
- [ ] Calendar MCP `search_events` passes query and time range to Google Calendar.
- [ ] Chat routes calendar prompts to Calendar agent when connected.
- [ ] Chat returns Settings guidance when Calendar is not connected.
- [ ] Calendar agent streams `tool_call_start` and `tool_call_result`.
- [ ] Existing Gmail behavior and tests continue to pass.
- [ ] Calendar write/delete requests are not executed without confirmation.

## Risks

- Google Calendar OAuth callback currently appears configured under `/api/auth/{tool}/callback`, while `.env.example` uses `/api/tools/{tool}/callback`; this mismatch should be corrected before manual OAuth testing.
- Existing Gmail code contains direct background sync API calls for notifications; this feature must avoid copying that pattern into chat execution.
- Agent tests may need lightweight mocks because MCP stdio and Gemini calls are external-process and network-adjacent.

## ADR Suggestion

Architectural decision detected: reusable per-tool MCP server plus specialist-agent pattern for platform integrations. Document reasoning and tradeoffs with `/sp.adr mcp-specialist-agent-pattern`.
