# Tasks: ByteOps Platform (Baseline)

**Input**: Design documents from `/specs/baseline/`
**Prerequisites**: plan.md (required), spec.md (required)

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US8)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project scaffolding and tooling

- [ ] T001 Initialize Next.js 15 project in `frontend/` (App Router, TypeScript, Tailwind CSS, `src/` dir)
- [ ] T002 Initialize Python backend in `backend/` via `uv init` + install core deps (FastAPI, uvicorn, SQLAlchemy, alembic, pydantic-settings)
- [ ] T003 [P] Create `.env.example` with all required environment variables
- [ ] T004 [P] Configure ESLint + Prettier for frontend
- [ ] T005 [P] Configure `ruff` linting for backend
- [ ] T006 [P] Set up Vitest for frontend testing
- [ ] T007 [P] Set up pytest + async fixtures for backend testing
- [ ] T008 Add `.gitignore` covering both frontend and backend

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work begins until this phase is complete

### Database & Config

- [ ] T009 Create `backend/app/core/config.py` — Pydantic settings (DB URL, Clerk keys, API keys)
- [ ] T010 Create `backend/app/core/database.py` — Async SQLAlchemy engine + session factory (Neon PostgreSQL)
- [ ] T011 Create `backend/app/models/user.py` — User model (id, clerk_id, email, display_name, avatar_url, preferences, created_at)
- [ ] T012 Create `backend/app/models/tool_connection.py` — ToolConnection model (id, user_id FK, tool_type, access_token, refresh_token, token_expires_at, scopes, status, metadata)
- [ ] T013 [P] Create `backend/app/models/conversation.py` — Conversation model (id, user_id FK, title, created_at, updated_at, is_archived)
- [ ] T014 [P] Create `backend/app/models/message.py` — Message model (id, conversation_id FK, role, content, tool_calls JSONB, created_at)
- [ ] T015 [P] Create `backend/app/models/notification.py` — Notification model (id, user_id FK, source_tool, title, content, priority, is_read, metadata JSONB, created_at)
- [ ] T016 Initialize Alembic in `backend/alembic/` and generate initial migration from models
- [ ] T017 Run migration against Neon PostgreSQL to verify schema

### Backend App Structure

- [ ] T018 Create `backend/app/main.py` — FastAPI app with CORS, lifespan events, router includes
- [ ] T019 [P] Create `backend/app/core/security.py` — Clerk JWT verification middleware + dependency
- [ ] T020 [P] Create `backend/app/api/__init__.py` — API router aggregation

### Frontend Foundation

- [ ] T021 Install Clerk SDK (`@clerk/nextjs`) and configure `ClerkProvider` in `frontend/src/app/layout.tsx`
- [ ] T022 Create auth routes: `frontend/src/app/(auth)/sign-in/[[...sign-in]]/page.tsx` and `sign-up` equivalent
- [ ] T023 Create middleware.ts for Clerk route protection (protect `/dashboard/*`)
- [ ] T024 Install core UI deps: `react-resizable-panels`, `lucide-react`, `clsx`, `tailwind-merge`
- [ ] T025 Create `frontend/src/lib/utils.ts` — `cn()` utility for class merging
- [ ] T026 Create `frontend/src/lib/api.ts` — API client (fetch wrapper with Clerk JWT injection)
- [ ] T027 Set up dark/light mode theme system in `globals.css` + ThemeProvider

**Checkpoint**: Auth works, database connected, API skeleton running, dashboard shell renders

---

## Phase 3: US1 — User Signs Up & Logs In (Priority: P1) 🎯 MVP

**Goal**: User can sign up/login via Clerk → land on protected dashboard → see empty state

**Independent Test**: Sign up → redirected to `/dashboard` → three-panel layout visible with welcome message

### Implementation

- [ ] T028 Create `frontend/src/components/layout/dashboard-shell.tsx` — Three-panel resizable layout (PanelGroup with left/middle/right)
- [ ] T029 [P] Create `frontend/src/components/layout/left-panel.tsx` — Empty tools list, chat history placeholder, "New Chat" button
- [ ] T030 [P] Create `frontend/src/components/layout/middle-panel.tsx` — Welcome message, suggested prompts, chat input area
- [ ] T031 [P] Create `frontend/src/components/layout/right-panel.tsx` — Tabbed interface (Workflows/Alerts/Tasks) with empty states
- [ ] T032 Create `frontend/src/app/(dashboard)/page.tsx` — Protected dashboard page rendering DashboardShell
- [ ] T033 Create `backend/app/api/auth.py` — Clerk webhook endpoint to sync user creation to PostgreSQL
- [ ] T034 Test: Sign up new user → verify user record created in DB → dashboard renders

**Checkpoint**: US1 complete — user can sign up, log in, and see the three-panel dashboard

---

## Phase 4: US2 — Connect a Tool via OAuth2 (Priority: P1)

**Goal**: User connects tools via OAuth2 → sees green status badge in left panel

**Independent Test**: Click "Connect Gmail" → complete OAuth → Gmail shows as "Connected" with green dot

### Implementation

- [ ] T035 Create `backend/app/services/tool_service.py` — Generic OAuth2 adapter: generate auth URL, handle callback, store tokens, refresh tokens
- [ ] T036 Create `backend/app/api/tools.py` — Endpoints: `GET /api/tools`, `POST /api/tools/:type/connect`, `GET /api/tools/:type/callback`, `DELETE /api/tools/:type/disconnect`
- [ ] T037 Implement Gmail OAuth2 config in `backend/app/services/oauth_configs/gmail.py`
- [ ] T038 [P] Implement GitHub OAuth2 config in `backend/app/services/oauth_configs/github.py`
- [ ] T039 [P] Implement JIRA OAuth2 config in `backend/app/services/oauth_configs/jira.py`
- [ ] T040 [P] Implement Slack OAuth2 config in `backend/app/services/oauth_configs/slack.py`
- [ ] T041 [P] Implement Trello OAuth2 config in `backend/app/services/oauth_configs/trello.py`
- [ ] T042 [P] Implement Dropbox OAuth2 config in `backend/app/services/oauth_configs/dropbox.py`
- [ ] T043 [P] Implement Calendar OAuth2 config in `backend/app/services/oauth_configs/calendar.py`
- [ ] T044 Create `frontend/src/components/tools/connect-tool-modal.tsx` — Modal with tool list and "Connect" buttons
- [ ] T045 Create `frontend/src/components/tools/tool-card.tsx` — Tool badge with status indicator + notification count
- [ ] T046 Update `left-panel.tsx` — Render connected tools from API, "Connect New Tool" button opens modal
- [ ] T047 Create `frontend/src/app/api/tools/[type]/callback/route.ts` — Next.js route to handle OAuth callback redirect
- [ ] T048 Implement token refresh service in `backend/app/services/token_refresh.py` — Auto-refresh expired tokens
- [ ] T049 Test: Connect Gmail → verify token stored → disconnect → verify token revoked

**Checkpoint**: US2 complete — all 7 tools connectable via OAuth2

---

## Phase 5: US3 — Chat with AI Assistant (Priority: P1)

**Goal**: User sends a message → AI processes via MCP → streams response → chat persists

**Independent Test**: "Summarize my unread emails" → AI calls Gmail MCP → streams summary

### MCP Infrastructure

- [ ] T050 Create `backend/app/mcp/config.py` — MCP server configurations per tool (command, args, env vars)
- [ ] T051 Create `backend/app/mcp/manager.py` — MCP client manager: connect to servers, discover tools, map tool→session, lifecycle management (based on DemoMCP patterns)
- [ ] T052 Create `backend/app/mcp/converters.py` — Convert MCP tool definitions ↔ OpenAI Agents SDK format

### Agent System

- [ ] T053 Install `openai-agents` in backend via `uv add openai-agents`
- [ ] T054 Create `backend/app/agents/orchestrator.py` — Central orchestrator agent: receives user message, routes to sub-agent, returns streaming response
- [ ] T055 Create `backend/app/agents/tools/email_agent.py` — Gmail sub-agent with MCP tool bindings
- [ ] T056 [P] Create `backend/app/agents/tools/github_agent.py` — GitHub sub-agent
- [ ] T057 [P] Create `backend/app/agents/tools/jira_agent.py` — JIRA sub-agent
- [ ] T058 [P] Create `backend/app/agents/tools/slack_agent.py` — Slack sub-agent
- [ ] T059 [P] Create `backend/app/agents/tools/trello_agent.py` — Trello sub-agent
- [ ] T060 [P] Create `backend/app/agents/tools/dropbox_agent.py` — Dropbox sub-agent
- [ ] T061 [P] Create `backend/app/agents/tools/calendar_agent.py` — Calendar sub-agent

### Chat API & Persistence

- [ ] T062 Create `backend/app/services/chat_service.py` — Create/list/get/delete conversations, add messages
- [ ] T063 Create `backend/app/api/chat.py` — Endpoints: `POST /api/chat` (SSE stream), `GET /api/conversations`, `GET /api/conversations/:id`, `DELETE /api/conversations/:id`
- [ ] T064 Create `backend/app/api/agents.py` — `POST /api/agents/confirm` endpoint for write action confirmation

### Frontend Chat UI

- [ ] T065 Create `frontend/src/components/chat/message-bubble.tsx` — Renders user/assistant messages with markdown, code blocks, tool call indicators
- [ ] T066 Create `frontend/src/components/chat/chat-input.tsx` — Textarea with send button, auto-resize, keyboard shortcuts
- [ ] T067 Create `frontend/src/components/chat/suggested-prompts.tsx` — Context-aware prompt cards based on connected tools
- [ ] T068 Create `frontend/src/components/chat/confirmation-card.tsx` — Card for confirming write/delete actions before execution
- [ ] T069 Create `frontend/src/hooks/use-chat.ts` — Hook managing SSE streaming, message state, conversation switching
- [ ] T070 Update `middle-panel.tsx` — Integrate chat components, SSE streaming, scroll management
- [ ] T071 Test: Send "Summarize my emails" → verify MCP tool call → verify streamed response → verify message persisted in DB

**Checkpoint**: US3 complete — full AI chat loop working with MCP tool execution and persistence

---

## Phase 6: US4 — Right Panel Activity Feed (Priority: P2)

**Goal**: Right panel shows notifications, tasks, workflows from connected tools

**Independent Test**: Connect JIRA → assigned tickets appear in "Tasks" tab automatically

### Implementation

- [ ] T072 Create `backend/app/services/notification_service.py` — Fetch/aggregate notifications from connected tools, mark as read
- [ ] T073 Create `backend/app/api/notifications.py` — `GET /api/notifications`, `PATCH /api/notifications/:id/read`
- [ ] T074 Create `backend/app/api/ws.py` — WebSocket endpoint for real-time notification push
- [ ] T075 Create `frontend/src/components/activity/notification-card.tsx` — Card showing source tool icon, priority badge, content, timestamp
- [ ] T076 [P] Create `frontend/src/components/activity/task-card.tsx` — Aggregated task card from JIRA/Trello/GitHub Issues
- [ ] T077 [P] Create `frontend/src/components/activity/workflow-card.tsx` — Workflow status card with toggle
- [ ] T078 Create `frontend/src/hooks/use-notifications.ts` — Hook managing WebSocket connection for real-time updates
- [ ] T079 Update `right-panel.tsx` — Integrate notification/task/workflow cards, WebSocket live updates
- [ ] T080 Test: Verify notifications appear from connected tools → mark as read → verify real-time update

**Checkpoint**: US4 complete — right panel shows live activity from connected tools

---

## Phase 7: US5 — Multi-Agent Task Execution (Priority: P2)

**Goal**: Cross-tool operations work via orchestrator handoffs with agent loop

**Independent Test**: "Create a JIRA ticket summarizing my latest email" → EmailAgent reads → JiraAgent creates → user confirms

### Implementation

- [ ] T081 Implement agent handoff logic in `orchestrator.py` — Route to sub-agents based on intent, chain results
- [ ] T082 Implement agent loop in `orchestrator.py` — Loop until task completion or user cancellation
- [ ] T083 Implement confirmation gate — Any write/delete surfaces confirmation to user via SSE before executing
- [ ] T084 Add agent error handling — Sub-agent failures reported clearly, orchestrator suggests alternatives
- [ ] T085 Test: Cross-tool scenario: "Create JIRA ticket from latest email" → verify both MCP servers called → confirmation shown → ticket created

**Checkpoint**: US5 complete — multi-agent cross-tool operations work

---

## Phase 8: US6 — Chat History Management (Priority: P2)

**Goal**: New chat, switch conversations, rename, delete — each with isolated context

**Independent Test**: Create 3 chats → switch between → verify isolated context

### Implementation

- [ ] T086 Update `left-panel.tsx` — Render chat history list from API, "New Chat" creates fresh conversation
- [ ] T087 Create `frontend/src/components/chat/chat-history-item.tsx` — History item with rename/delete actions
- [ ] T088 Implement conversation context loading in `use-chat.ts` — Switch loads full message history, continues from where user left off
- [ ] T089 Test: Create chat → switch to new → switch back → verify messages preserved and continuable

**Checkpoint**: US6 complete — chat history fully functional

---

## Phase 9: US7 — Suggested Actions & Quick Prompts (Priority: P3)

**Goal**: Context-aware suggested prompts based on connected tools and activity

### Implementation

- [ ] T090 Create `backend/app/services/suggestion_service.py` — Generate suggested actions based on connected tools + recent notifications
- [ ] T091 Create `backend/app/api/suggestions.py` — `GET /api/suggestions` endpoint
- [ ] T092 Update `suggested-prompts.tsx` — Fetch from API, show contextual prompts
- [ ] T093 Implement right-panel suggested actions — Clickable actions that pre-fill chat input
- [ ] T094 Test: Connect Gmail + JIRA → verify relevant prompts appear → clicking fills chat input

**Checkpoint**: US7 complete — context-aware suggestions working

---

## Phase 10: US8 — SKILLS System (Priority: P3)

**Goal**: Pre-built prompt templates reduce token usage for common operations

### Implementation

- [ ] T095 Create `backend/app/models/skill.py` — Skill model (name, description, tool_type, template)
- [ ] T096 Create `backend/app/agents/skills/` — Skill templates for common operations (summarize-emails, list-tickets, etc.)
- [ ] T097 Implement SKILL matching in `orchestrator.py` — Check for matching skill before raw MCP calls
- [ ] T098 Seed database with initial SKILLS (summarize-emails, list-open-tickets, recent-commits, unread-messages)
- [ ] T099 Test: Compare token usage with vs. without SKILLS for "Summarize my emails" query

**Checkpoint**: US8 complete — SKILLS reduce token usage for common queries

---

## Phase 11: Polish & Cross-Cutting Concerns

- [ ] T100 Error handling audit — All API endpoints return proper error responses
- [ ] T101 [P] Edge case: OAuth token expiry mid-conversation — auto-refresh or prompt
- [ ] T102 [P] Edge case: MCP server unreachable — graceful degradation message
- [ ] T103 [P] Edge case: Rate limiting from tool APIs — backoff and user notification
- [ ] T104 Performance optimization — query optimization, connection pooling, caching
- [ ] T105 [P] Live deployment — Deploy frontend to Vercel, backend to Railway/Render
- [ ] T106 E2E tests with Playwright — Sign up → connect tool → chat → verify response

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — BLOCKS all user stories
- **Phases 3-10 (User Stories)**: All depend on Phase 2 completion
  - US1 (P1) → US2 (P1) → US3 (P1) → then P2/P3 stories
  - US4, US5, US6 can proceed in parallel after US3
  - US7, US8 can proceed in parallel after US5
- **Phase 11 (Polish)**: After all desired stories complete

### Within Each User Story

- Models → Services → API endpoints → Frontend components → Integration test
- [P] tasks within a phase can run in parallel

---

## Notes

- Total: 106 tasks across 11 phases
- P1 stories (US1-US3) are the critical path — ~55 tasks
- All [P] marked tasks can run concurrently
- Commit after each task or logical group
- Stop at any checkpoint to validate independently
