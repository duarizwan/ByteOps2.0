# Feature Specification: UI Polish — Chat Feedback, Status Badges, Error States, Loading

**Feature Branch**: `2-ui-polish`  
**Created**: 2026-05-31  
**Status**: Draft  
**Input**: User description: "UI polish — chat progress feedback (inline bubble), activity status badges, graceful error states, loading transitions"

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Chat Progress Feedback (Priority: P1)

A user sends a message and watches the assistant bubble show human-readable stage labels — "Understanding request…", "Routing to specialist agent…", "Preparing action…", "Waiting for approval…", "Finalizing response…" — in place of a generic spinner, then the labels resolve into the final reply text.

**Why this priority**: The most visible UX gap. Users currently see opaque loading dots with no sense of progress or expected wait time. Stage labels immediately convey that the system is working intelligently.

**Independent Test**: Can be tested by sending any chat message and confirming stage text appears and transitions correctly, with no impact on other chat functionality.

**Acceptance Scenarios**:

1. **Given** the user sends a chat message, **When** the backend begins processing, **Then** the assistant bubble shows "Understanding request…" immediately (within 300 ms of send).
2. **Given** the AI is routing to an agent, **When** a tool call starts, **Then** the label updates to "Routing to specialist agent…" inside the same bubble.
3. **Given** an action requires approval, **When** the approval event arrives, **Then** the label updates to "Waiting for approval…".
4. **Given** the AI has finished, **When** the response streams in, **Then** the stage label disappears and the final text renders in its place.
5. **Given** the AI fails or times out, **When** the error occurs, **Then** the bubble shows an error state (covered by User Story 3) rather than freezing on a stage label.

---

### User Story 2 — Activity Status Badges and Prominent Trace Button (Priority: P2)

A user opens the Action Center and can immediately see the status of each action card (Completed / Pending Approval / Failed / Waiting) via a colour-coded badge, and can reach the trace view with a clearly visible button rather than a subtle link.

**Why this priority**: The Action Center is the primary review surface. Without status at a glance, users must open each card to understand its state.

**Independent Test**: Can be tested by loading the Action Center with cards in different states and confirming badges render correctly and the trace button is accessible.

**Acceptance Scenarios**:

1. **Given** an action card is in a completed state, **When** the Action Center loads, **Then** the card shows a "Completed" badge in a visually distinct style.
2. **Given** an action card is awaiting approval, **When** the Action Center loads, **Then** the card shows a "Pending Approval" badge.
3. **Given** an action card encountered an error, **When** the Action Center loads, **Then** the card shows a "Failed" badge.
4. **Given** an action card is waiting on a dependency, **When** the Action Center loads, **Then** the card shows a "Waiting" badge.
5. **Given** any action card, **When** the user wants to inspect the trace, **Then** the trace button is visually prominent and clearly labelled (not a small link text).
6. **Given** the user clicks the trace button, **When** the trace overlay opens, **Then** the full trace is shown (existing behaviour, not regressed).

---

### User Story 3 — Graceful Error States (Priority: P2)

A user encounters a service-level problem (OAuth not connected, no data found, AI timeout, MCP unavailable, backend down) and sees a friendly, actionable message rather than a raw error or blank state.

**Why this priority**: Bare errors undermine trust in demos and production. Friendly messages tell users what happened and what they can do next.

**Independent Test**: Can be tested by simulating each error condition (e.g., disconnecting Gmail OAuth, killing the backend) and confirming friendly UI messages appear.

**Acceptance Scenarios**:

1. **Given** the user's Gmail OAuth token is missing or expired, **When** the AI tries to access Gmail, **Then** the chat shows a message like "Gmail isn't connected. Go to Settings → Integrations to reconnect."
2. **Given** a query returns no matching emails or items, **When** the agent responds, **Then** the UI shows "No results found" rather than an empty list with no explanation.
3. **Given** the AI agent times out, **When** the timeout occurs, **Then** the chat shows "This took longer than expected. Please try again."
4. **Given** an MCP server is unavailable, **When** the agent tries to use it, **Then** the user sees "The [tool] service is temporarily unavailable."
5. **Given** the backend is completely unreachable, **When** the user tries to chat, **Then** the UI shows "Can't reach ByteOps. Check your connection and retry." rather than a loading spinner that never resolves.
6. **Given** any actionable error (OAuth missing), **When** the user reads the message, **Then** the message includes a link or button to the resolution path (e.g., Settings page).

---

### User Story 4 — Loading Transitions for Action Center and Trace View (Priority: P3)

A user navigates to the Action Center or opens a trace and sees a skeleton loading state instead of a blank or partially-rendered page while data is fetching.

**Why this priority**: Skeletons eliminate jarring blank-screen flashes. Lower priority than the above because the Action Center loads quickly on average, but important for slower connections and demo polish.

**Independent Test**: Can be tested by throttling the network to simulate slow loads and confirming skeleton placeholders appear before content.

**Acceptance Scenarios**:

1. **Given** the user navigates to the Action Center, **When** action cards are still loading, **Then** skeleton card shapes appear in place of real cards.
2. **Given** the cards load, **When** data arrives, **Then** skeletons fade/transition out and real cards render without layout shift.
3. **Given** the user opens the trace view, **When** trace data is loading, **Then** a skeleton or spinner renders inside the trace overlay.
4. **Given** the trace data loads, **When** it arrives, **Then** the trace content replaces the skeleton without the overlay closing and reopening.

---

### Edge Cases

- What happens if the SSE connection drops mid-stream while a stage label is showing? The bubble should freeze on the last known label and transition to an error state after a timeout.
- What happens if a stage event is received out of order? Labels should advance only forward; stale events must not cause regression to an earlier label.
- What happens if the Action Center has zero cards? The loading skeleton should give way to an empty state message, not a blank page.
- What happens if the backend returns an HTTP error for the trace? The trace overlay must show an error message rather than hanging on a spinner.
- What happens if a badge status is unknown/unmapped? Fall back to a neutral "In Progress" badge rather than rendering nothing.

---

## Requirements *(mandatory)*

### Functional Requirements

**Chat Progress Feedback (P1)**

- **FR-001**: The assistant message bubble MUST display stage labels during AI processing, replacing the current loading indicator.
- **FR-002**: Stage labels MUST map to SSE events: `tool_call_start` → "Routing to specialist agent…", `approval_required` → "Waiting for approval…", final response → label clears.
- **FR-003**: An initial label "Understanding request…" MUST appear within 300 ms of the user sending a message, before any SSE event arrives.
- **FR-004**: Labels MUST transition forward only — no regression to earlier stages on late-arriving events.
- **FR-005**: When the final text streams in, the stage label MUST be replaced by the response text with no visible flash or layout shift.

**Activity Status Badges (P2)**

- **FR-006**: Each ActionCard MUST display a status badge from the set: Completed, Pending Approval, Failed, Waiting.
- **FR-007**: Badge styling MUST be visually distinct per status (colour differentiation at minimum).
- **FR-008**: The trace navigation element on each ActionCard MUST be styled as a prominent button, not a text link.
- **FR-009**: Badge status MUST derive from the card's existing data model with no new API calls required.

**Graceful Error States (P2)**

- **FR-010**: The chat interface MUST display a user-friendly message for each identified error class: OAuth missing, no results found, AI timeout, MCP unavailable, backend unreachable.
- **FR-011**: Error messages for actionable errors (OAuth, settings) MUST include a link to the resolution path.
- **FR-012**: Error messages MUST NOT expose raw error codes, stack traces, or technical identifiers to users.
- **FR-013**: After displaying an error, the chat input MUST remain enabled so the user can retry.

**Loading Transitions (P3)**

- **FR-014**: The Action Center MUST display skeleton card placeholders while cards are loading.
- **FR-015**: The trace view MUST display a skeleton or spinner while trace data is loading.
- **FR-016**: Skeleton transitions to content MUST not cause layout shift.

### Key Entities

- **Stage Label**: A transient UI state in the assistant bubble representing the current processing phase; driven by SSE event type.
- **Status Badge**: A persistent visual indicator on an ActionCard representing the terminal or current state of an action.
- **Error Class**: A categorised failure mode (OAuth, no-results, timeout, MCP, backend-down) with a defined user-facing message template.
- **Skeleton Placeholder**: A loading-state UI element that mirrors the shape of the content it will replace.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users see a stage label within 300 ms of sending a chat message — confirmed by visual inspection at normal network speed.
- **SC-002**: 100% of ActionCards in the Action Center display a status badge with no cards showing an "unknown" or empty badge state.
- **SC-003**: All 5 identified error classes (OAuth, no-results, timeout, MCP, backend-down) show a friendly message rather than a raw error or blank state.
- **SC-004**: The Action Center shows skeleton placeholders on every load; no blank-screen flash on a throttled (Slow 3G) network.
- **SC-005**: All existing Action Center tests continue to pass after changes (zero regression).
- **SC-006**: Stage label transitions have no visible layout shift in the chat bubble — verified by Cumulative Layout Shift remaining at 0 for the chat column.

---

## Assumptions

- Existing SSE events (`tool_call_start`, `approval_required`, `done`) are sufficient to drive stage labels; no new backend events are required.
- ActionCard status can be derived from existing card data (state/type fields) without new API endpoints.
- Error class detection happens at the frontend SSE/API layer by examining event payloads or HTTP status codes already received.
- Skeleton shape for ActionCards mirrors the current card dimensions; no design spec is needed beyond proportional placeholders.
- The trace view overlay already handles open/close state; only internal loading state needs skeleton treatment.

---

## Out of Scope

- Adding new SSE event types or modifying the backend event schema.
- Redesigning the Action Center layout or card structure beyond badges and trace button prominence.
- Internationalisation of error messages or stage labels.
- Retry logic or automatic re-connection on error (only the UI messaging is in scope).
