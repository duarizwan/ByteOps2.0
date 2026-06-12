# Feature Specification: Agent Runs Graph Page

**Feature Branch**: `1-agent-runs-graph`
**Created**: 2026-05-30
**Status**: Draft

---

## User Scenarios & Testing

### User Story 1 — View execution trace for a completed run (Priority: P1)

A developer or power user opens the Runs page from the sidebar, sees a list of recent agent runs on the left, selects one, and the right panel renders a directed graph showing exactly what the agent did: which intent was detected, which tools were called, which external platform APIs were hit, whether anything was written to the database, and the final response. They can read the full trace without digging into logs.

**Why this priority**: Core value of the feature. Everything else is secondary to seeing a run's trace clearly.

**Independent Test**: Navigate to `/runs`, select any completed run, verify the graph renders with at least a User Input node and a Final Response node connected by edges.

**Acceptance Scenarios**:

1. **Given** a completed gmail agent run exists, **When** the user opens `/runs` and clicks that run, **Then** a directed graph appears showing nodes for User Input → Intent Router → Agent Plan → tool calls → Platform API hits → DB Write → Final Response, connected by bezier-curve edges with arrowheads.
2. **Given** a run with two parallel tool calls, **When** the graph renders, **Then** the two tool nodes appear side by side, both branching from the Plan node and both converging into the DB Write node.
3. **Given** a failed run, **When** the user selects it, **Then** the graph renders up to the failure point and the failing node is visually distinguished (red left-border accent).

---

### User Story 2 — Inspect a specific node's detail (Priority: P2)

The user clicks any node in the graph and a detail popup appears anchored near that node. The popup shows the node type, risk level (READ / WRITE / DESTRUCTIVE / EXTERNAL_SEND), duration in milliseconds, completion status, and the exact input parameters and output payload for that step — all in a concise, readable format. They can close the popup with × and click a different node.

**Why this priority**: Without this, the graph is decorative. Node detail is what makes it actionable for debugging.

**Independent Test**: Click the `search_emails` tool-call node on any gmail run — popup appears with risk: READ, duration, input query, and output count.

**Acceptance Scenarios**:

1. **Given** the graph is rendered, **When** the user clicks a Tool Call node, **Then** a popup appears showing: type label, risk level with colour indicator, duration, status, input payload, and output payload.
2. **Given** the popup is open, **When** the user clicks ×, **Then** the popup closes and the node returns to its default visual state.
3. **Given** the popup is open, **When** the user clicks a different node, **Then** the popup updates to show that node's details.
4. **Given** a node with no output (e.g. a failed step), **When** the popup opens, **Then** the output section shows the error message instead.

---

### User Story 3 — Dismiss runs individually or clear all (Priority: P2)

The user hovers over any run row in the left panel and a × dismiss button appears. Clicking it removes that run from the list without affecting others. A "Clear all" button at the top of the list removes all run rows. Dismissed runs are hidden from the UI for the session; they remain in the database and reappear on next page load unless explicitly deleted.

**Why this priority**: Without dismiss, the list fills with every chat message sent, making the page unusable over time.

**Independent Test**: Hover a run row — × appears. Click it — row is removed. Other rows remain. Click "Clear all" — list is empty.

**Acceptance Scenarios**:

1. **Given** multiple run rows are listed, **When** the user hovers a row, **Then** a × button appears on the right of that row.
2. **Given** a run row is hovered, **When** the user clicks ×, **Then** that row is removed from the list; remaining rows are unaffected.
3. **Given** runs are listed, **When** the user clicks "Clear all", **Then** all rows are removed and an empty state is shown.
4. **Given** the selected run is dismissed, **When** it is removed, **Then** the graph panel shows an empty state or auto-selects the next available run.

---

### User Story 4 — Theme switches automatically (Priority: P3)

The user toggles between light and dark mode using the existing theme control in the top bar. The Runs page — including the graph canvas, all nodes, edges, the runs list panel, and the node detail popup — updates instantly to match the selected theme without a page reload.

**Why this priority**: Consistency requirement. The rest of the app already supports theme switching; the new page must not be the odd one out.

**Independent Test**: While on `/runs` with a graph visible, toggle the theme — all node colours, canvas background, panel backgrounds, and text switch immediately.

**Acceptance Scenarios**:

1. **Given** the app is in dark mode and a graph is rendered, **When** the user switches to light mode, **Then** all node backgrounds, border colours, canvas background, panel backgrounds, and popup styles update without a page reload.
2. **Given** the app is in light mode, **When** the user switches to dark mode, **Then** the same elements switch back correctly.

---

### Edge Cases

- What happens when a run has zero recorded steps (e.g. it failed before planning)? → Show only the User Input node and an error node with the failure message.
- What happens when the runs list is empty? → Show an empty state: "No agent runs yet. Send a message in chat to see traces here."
- What happens when `/api/agent-runs/{id}` returns a 404 (run was deleted from DB)? → Show an inline error in the graph panel; do not crash the page.
- What happens when a tool call node has a very large input or output payload? → Truncate to 500 characters in the popup with a "show full" toggle.
- What happens when the graph has many parallel tool calls (e.g. 6+)? → Nodes overflow horizontally; the canvas must be scrollable/pannable.
- What if the user is on a narrow viewport? → The runs list panel collapses to an icon-only strip; tapping an icon expands it as a drawer overlay.

---

## Requirements

### Functional Requirements

- **FR-001**: The application MUST provide a dedicated route (`/runs`) accessible from the main sidebar navigation via a persistent icon.
- **FR-002**: The `/runs` page MUST display a scrollable list of the current user's agent runs, ordered by most recent first, limited to the 50 most recent.
- **FR-003**: Each run row MUST display: intent label (e.g. "gmail"), completion status with a colour-coded dot (green = completed, red = failed, amber = awaiting approval), and relative timestamp.
- **FR-004**: Each run row MUST reveal a dismiss (×) button on hover; clicking it MUST remove the row from the list for the current session.
- **FR-005**: A "Clear all" button MUST be present at the top of the runs list and MUST remove all run rows from the current view when clicked.
- **FR-006**: Clicking a run row MUST render that run's execution trace as a directed acyclic graph in the right panel, replacing any previously displayed graph.
- **FR-007**: The graph MUST represent each recorded agent step as a node, with directed edges indicating execution order and data flow.
- **FR-008**: The graph MUST support the following node types, each visually distinguished by a unique left-border accent colour, a labelled type badge, and an inline SVG icon: User Input, Intent Router, Agent Plan, Tool Call, Platform API, DB Write, Final Response.
- **FR-008a**: All graph nodes MUST be rendered in an **ellipse (oval) shape** — not rectangular cards. The ellipse dimensions MUST be wide enough to accommodate the node label and type badge comfortably (minimum 160 × 64 px).
- **FR-008b**: Node spacing MUST be generous: a minimum of **120 px vertical gap** between sequential node rows and **160 px horizontal gap** between parallel sibling nodes, so edges are clearly readable and nodes never feel crowded.
- **FR-009**: Node names (e.g. `search_emails`, `intent_router`) MUST be rendered in a monospace typeface to signal they represent function/tool identifiers.
- **FR-010**: Metadata within each node (risk level, duration, status) MUST be displayed as pill badges.
- **FR-011**: Parallel tool calls (steps that ran concurrently) MUST be rendered side by side, branching from a shared parent node and converging to a shared child node.
- **FR-012**: Edges MUST be rendered as smooth bezier curves with directional arrowheads.
- **FR-013**: Clicking any node MUST open a detail popup anchored near that node, showing: type, risk level, duration, status, input payload, and output payload (or error message if the step failed).
- **FR-014**: The detail popup MUST be closeable via a × button. Clicking another node MUST move the popup to that node.
- **FR-015**: The graph canvas MUST support zoom in/out and pan; zoom controls MUST be accessible via on-canvas buttons and scroll wheel.
- **FR-016**: A "Fit view" button MUST be present in the graph panel top bar and MUST reset the viewport to show the entire graph.
- **FR-017**: The entire page — nodes, edges, panels, popup — MUST respond automatically to the application's light/dark theme toggle without any page reload, using the existing CSS variable system (`var(--card)`, `var(--border)`, `var(--primary)`, etc.).
- **FR-018**: The page MUST fetch run data from the existing `GET /api/agent-runs` and `GET /api/agent-runs/{id}` endpoints using the authenticated user's session token.
- **FR-019**: The runs list MUST poll for new runs every 30 seconds so newly completed runs appear without a manual refresh.

### Key Entities

- **AgentRun**: A single end-to-end execution triggered by one user message. Has an intent label, status, timestamps, and an ordered list of steps. Source: existing `AgentRun` model and `/api/agent-runs` endpoint.
- **AgentRunStep**: One recorded action within a run (route decision, plan, tool call, DB write, final response). Has a `step_type` enum, name, input payload, output payload, duration, and status. Source: existing `AgentRunStep` model, returned nested inside `AgentRun`.
- **GraphNode**: A frontend-only representation of one `AgentRunStep` (or a synthesised node such as User Input) positioned on the React Flow canvas. Has a type, position, and data payload for rendering.
- **GraphEdge**: A frontend-only directed connection between two `GraphNode` instances, derived from the sequential/parallel ordering of `AgentRunStep` records.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: A developer can identify which tool call caused a failure in a given agent run in under 30 seconds, using only the graph and node detail popup.
- **SC-002**: The graph for a typical run (4–6 tool call steps) renders fully within 1 second of selecting the run from the list.
- **SC-003**: The runs list remains usable (not overwhelming) after 20+ runs have accumulated — achievable via per-row dismiss and "Clear all".
- **SC-004**: Theme switching causes zero visual inconsistency — no hardcoded colours remain visible after toggling.
- **SC-005**: The page works correctly for all six platform integrations (Gmail, Slack, GitHub, Jira, Calendar, Dropbox) without platform-specific code in the graph renderer.

---

## Assumptions

- Dismiss is a client-side-only operation (hide from view for the session). Runs are not deleted from the database. A future "delete run" feature can address permanent removal.
- The existing `AgentRunStep.step_type` values (`route`, `plan`, `tool_call`, `approval`, `verify`, `final`) map 1:1 to graph node types, with `tool_call` steps further split into Tool Call and Platform API nodes based on whether the step name ends with `_api` or similar convention.
- The `input` and `output` fields on `AgentRunStep` contain serialisable JSON objects suitable for display in the popup without additional transformation.
- Parallel tool calls are identified by grouping consecutive `tool_call` steps with no intervening non-tool steps.
- The `/runs` route is a new Next.js page at `frontend/src/app/(dashboard)/runs/page.tsx`, consistent with the existing dashboard layout.
- The `@xyflow/react` package will be added as a new frontend dependency. No backend changes are required.
