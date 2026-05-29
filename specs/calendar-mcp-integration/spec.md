# Feature Specification: Calendar MCP Integration

**Feature Branch**: `calendar-mcp-integration`  
**Created**: 2026-05-26  
**Status**: Draft  
**Input**: User wants ByteOps to integrate major platforms one by one using MCP servers only; Gmail is connected now, and Calendar should be the first reusable non-Gmail integration slice.

## User Scenarios & Testing

### User Story 1 - Connect Google Calendar (Priority: P1)

A logged-in user connects Google Calendar from Settings and sees Calendar marked as connected without breaking the existing Gmail connection flow.

**Why this priority**: Calendar access is required before the AI can answer schedule questions or use Calendar as a tool.

**Independent Test**: Sign in, click Connect on Google Calendar, complete Google OAuth consent, return to Settings, and verify Calendar is listed as connected.

**Acceptance Scenarios**:

1. **Given** a logged-in user with no Calendar connection, **When** they click Connect for Google Calendar, **Then** ByteOps redirects them to Google OAuth with Calendar scopes.
2. **Given** Google OAuth succeeds, **When** the callback returns, **Then** ByteOps stores a connected Calendar ToolConnection for that user and redirects back to Settings with a success state.
3. **Given** Calendar OAuth credentials are missing, **When** the user clicks Connect, **Then** ByteOps shows a clear setup error and does not show Calendar as connected.
4. **Given** Calendar is connected, **When** the user clicks Disconnect, **Then** Calendar is marked disconnected and no longer appears as an active tool.

---

### User Story 2 - Ask About Upcoming Events (Priority: P1)

A user asks the ByteOps AI about their schedule, and the assistant calls the Calendar MCP server to retrieve real Calendar events.

**Why this priority**: This proves the reusable integration spine beyond Gmail: intent detection, specialist agent routing, MCP tool discovery, tool execution, SSE streaming, and persisted chat.

**Independent Test**: With Calendar connected, send "What's on my calendar today?" and verify the assistant returns event titles, times, and calendar names from the user's real Google Calendar.

**Acceptance Scenarios**:

1. **Given** Calendar is connected, **When** the user asks "What's on my calendar today?", **Then** ByteOps routes the request to the Calendar specialist agent.
2. **Given** the Calendar specialist agent starts, **When** it initializes its MCP subprocess, **Then** it discovers Calendar tools through MCP instead of using direct frontend or chat API wrappers.
3. **Given** events exist in the requested time range, **When** the MCP tool returns them, **Then** the assistant summarizes them with event title, start time, end time, calendar name, and meeting link when present.
4. **Given** no events exist in the requested time range, **When** the user asks for their schedule, **Then** the assistant says no matching events were found and suggests a broader range.

---

### User Story 3 - Search Calendar Events (Priority: P2)

A user asks for specific meetings or events, and ByteOps searches Calendar through the MCP server.

**Why this priority**: Search is the next useful read-only operation after listing upcoming events and exercises query parameters safely.

**Independent Test**: With Calendar connected, send "Find my meetings with ByteOps this week" and verify matching events are returned.

**Acceptance Scenarios**:

1. **Given** Calendar is connected, **When** the user asks for events matching a phrase, **Then** the Calendar MCP server searches events by text and time range.
2. **Given** multiple matching events exist, **When** results are returned, **Then** the assistant groups them in chronological order.
3. **Given** the provider returns a rate-limit or permission error, **When** search fails, **Then** the assistant explains the failure and suggests reconnecting or trying later.

---

### User Story 4 - Prepare Calendar Write Actions (Priority: P3)

A user asks to create, update, or delete a Calendar event, and ByteOps prepares a confirmation instead of executing the write immediately.

**Why this priority**: The constitution requires explicit confirmation for write/delete actions. This story defines the safety behavior before write tools are enabled broadly.

**Independent Test**: Ask "Schedule a meeting tomorrow at 10 with duarizwan098@gmail.com" and verify ByteOps shows the proposed event details for confirmation before any Calendar write tool is called.

**Acceptance Scenarios**:

1. **Given** Calendar is connected, **When** the user asks to create an event, **Then** ByteOps extracts title, date, time, attendees, description, and meeting link preference into a pending confirmation.
2. **Given** required event details are missing, **When** the user asks to schedule an event, **Then** ByteOps asks one concise clarifying question before preparing confirmation.
3. **Given** the user has not confirmed, **When** a Calendar write/delete action is available, **Then** ByteOps does not call the write/delete MCP tool.

## Edge Cases

- If the Calendar token expires during a chat request, ByteOps marks the connection expired or refreshes it using the stored refresh token before retrying once.
- If Google Calendar returns 401 or insufficient-scope errors, ByteOps tells the user to reconnect Calendar and does not retry repeatedly.
- If the Calendar MCP subprocess fails to start, ByteOps streams a clear tool-unavailable error and preserves the conversation.
- If the user asks a calendar question without Calendar connected, ByteOps guides them to Settings to connect Google Calendar.
- If the user has multiple calendars, list/search results include the calendar name or id so events are not ambiguous.
- If a user disconnects Calendar while a chat request is running, the in-flight operation fails gracefully and no token from another user is used.

## Requirements

### Functional Requirements

- **FR-001**: System MUST support Google Calendar OAuth connection using per-user OAuth tokens stored as ToolConnection rows with `tool_type=calendar`.
- **FR-002**: System MUST use MCP tools for Calendar event reads; chat execution MUST NOT call Google Calendar APIs directly outside the Calendar MCP server.
- **FR-003**: System MUST expose a Calendar MCP server with a `list_events` tool that accepts a time range and returns normalized event summaries.
- **FR-004**: System MUST expose a Calendar MCP server with a `search_events` tool that accepts query text, optional calendar id, and a time range.
- **FR-005**: System MUST add a Calendar specialist agent that discovers MCP tools at runtime and executes them through an MCP ClientSession.
- **FR-006**: System MUST route calendar-related user messages from the orchestrator to the Calendar specialist when Calendar is connected.
- **FR-007**: System MUST stream Calendar tool-call start and result events through the existing SSE chat protocol.
- **FR-008**: System MUST persist the final assistant response in the active conversation after Calendar tool execution.
- **FR-009**: System MUST show Calendar connection status in Settings using the same connection hook as Gmail.
- **FR-010**: System MUST require explicit user confirmation before any Calendar create, update, or delete tool is called.
- **FR-011**: System MUST preserve existing Gmail behavior while adding Calendar behavior.
- **FR-012**: System MUST provide tests for OAuth initiation, intent routing, Calendar agent tool execution, and disconnected-tool error handling.

### Key Entities

- **ToolConnection**: Existing per-user OAuth connection record. Calendar uses `tool_type=calendar`, access token, refresh token, scopes, status, and token expiry.
- **CalendarEventSummary**: Normalized event returned by MCP tools. Includes event id, calendar id or name, title, start time, end time, location, attendees, meeting link, and status when available.
- **Conversation**: Existing chat thread receiving user schedule questions and assistant responses.
- **Message**: Existing persisted chat message. Calendar assistant responses are saved like Gmail and general responses.
- **PendingCalendarAction**: Proposed write action details awaiting user confirmation before any create/update/delete MCP tool call. This feature specifies the safety contract; full execution can be implemented in a later write-action slice.

## Constraints, Invariants, and Non-Goals

- All Calendar AI operations must flow through MCP servers only.
- OAuth credentials and tokens must never be hardcoded.
- Calendar data must remain isolated per authenticated Clerk user.
- The first implementation slice should prioritize read-only `list_events` and `search_events`.
- UI modernization is out of scope except for changes required to connect and test Calendar.
- Slack, GitHub, JIRA, and Dropbox integrations are out of scope for this feature, but the implementation should establish a reusable pattern for them.
- Background Calendar notification sync is out of scope for the first slice.
- Mobile responsiveness improvements are out of scope until the core integration is working.

## Success Criteria

### Measurable Outcomes

- **SC-001**: A test user can connect Google Calendar and see Calendar marked connected in Settings in under 2 minutes after OAuth credentials are configured.
- **SC-002**: A connected user asking "What's on my calendar today?" receives a real Calendar-backed response without a server error.
- **SC-003**: Calendar read responses stream through the existing `/api/chat` SSE endpoint and persist in chat history.
- **SC-004**: Existing Gmail tests and manual Gmail chat behavior remain functional after Calendar integration.
- **SC-005**: Calendar write/delete requests do not execute provider-side changes without explicit user confirmation.
- **SC-006**: The backend returns a clear user-facing message when Calendar is not connected, credentials are missing, or the MCP server is unavailable.
