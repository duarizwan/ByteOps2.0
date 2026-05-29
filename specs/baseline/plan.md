# Implementation Plan: ByteOps Platform (Baseline)

**Branch**: `main` | **Date**: 2026-02-24 | **Spec**: [spec.md](file:///d:/uni/FYP/ByteOps/specs/baseline/spec.md)

## Summary

ByteOps is an AI-powered middleware platform that consolidates business tools (Gmail, Slack, JIRA, GitHub, Trello, Dropbox, Calendar) into a single dashboard with a multi-agent AI system connected via MCP servers. This plan covers the full-stack architecture, data model, and a phased 14-16 week build roadmap.

## Technical Context

**Frontend**: Next.js 15 (App Router, TypeScript, Tailwind CSS)  
**Backend**: Python 3.12+ (FastAPI, managed via `uv`)  
**AI Orchestration**: OpenAI Agents SDK with Google Gemini API  
**Tool Integration**: MCP servers (stdio via Docker)  
**Database**: PostgreSQL (Neon — cloud-hosted)  
**Auth**: Clerk (Email/Password, Google)  
**Real-time**: SSE (AI streaming), WebSockets (notifications)  
**Testing**: `pytest` (backend), `Vitest` (frontend)  
**Deployment**: Vercel (frontend) + Railway/Render (backend, free tier)  
**Performance Goals**: AI response < 3s (p95), cross-tool ops < 10s (p95), 50 concurrent users  
**Constraints**: Free-tier hosting, Gemini API free tier for development

## Constitution Check

| Principle | Status |
|---|---|
| I. AI-First Middleware | ✅ MCP-based tool integration, AI as primary interface |
| II. Multi-Agent Architecture | ✅ Orchestrator → Sub-agents → SKILLS |
| III. Three-Panel Dashboard | ✅ Resizable layout with dark mode |
| IV. Test-First (TDD) | ✅ pytest + Vitest, specs before code |
| V. Security by Design | ✅ Clerk + OAuth2, encrypted tokens, per-user isolation |
| VI. Production-Grade | ✅ Neon PostgreSQL, persistent everything, live deployment |

## Project Structure

```text
ByteOps/
├── frontend/                       # Next.js 15 application
│   ├── src/
│   │   ├── app/                    # App Router pages
│   │   │   ├── (auth)/             # Auth routes (sign-in, sign-up)
│   │   │   ├── (dashboard)/        # Protected dashboard routes
│   │   │   │   └── page.tsx        # Main dashboard
│   │   │   ├── api/                # Next.js API routes (BFF)
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── layout/             # DashboardShell, panels
│   │   │   ├── chat/               # MessageBubble, ChatInput, SuggestedPrompts
│   │   │   ├── tools/              # ToolCard, ConnectToolModal, OAuthCallback
│   │   │   ├── activity/           # NotificationCard, TaskCard, WorkflowCard
│   │   │   └── ui/                 # Shared UI primitives
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── lib/                    # Utilities, API client, types
│   │   └── stores/                 # Client state (Zustand or Context)
│   ├── tests/
│   └── package.json
│
├── backend/                        # Python FastAPI application
│   ├── app/
│   │   ├── api/                    # FastAPI routers
│   │   │   ├── auth.py             # Auth endpoints (Clerk webhook)
│   │   │   ├── chat.py             # Chat/conversation endpoints
│   │   │   ├── tools.py            # Tool connection endpoints
│   │   │   ├── agents.py           # Agent execution endpoints (SSE)
│   │   │   └── notifications.py    # Notification/activity endpoints
│   │   ├── agents/                 # Agent system
│   │   │   ├── orchestrator.py     # Central routing agent
│   │   │   ├── tools/              # Specialized tool agents
│   │   │   │   ├── email_agent.py
│   │   │   │   ├── jira_agent.py
│   │   │   │   ├── github_agent.py
│   │   │   │   ├── slack_agent.py
│   │   │   │   └── ...
│   │   │   └── skills/             # Pre-built prompt templates
│   │   ├── mcp/                    # MCP client management
│   │   │   ├── manager.py          # Session lifecycle, tool discovery
│   │   │   └── config.py           # Server configs per tool
│   │   ├── models/                 # SQLAlchemy/Pydantic models
│   │   │   ├── user.py
│   │   │   ├── conversation.py
│   │   │   ├── tool_connection.py
│   │   │   └── notification.py
│   │   ├── services/               # Business logic layer
│   │   │   ├── chat_service.py
│   │   │   ├── tool_service.py
│   │   │   └── notification_service.py
│   │   ├── core/                   # Config, security, database
│   │   │   ├── config.py           # Pydantic settings
│   │   │   ├── database.py         # Async SQLAlchemy + Neon
│   │   │   └── security.py         # Clerk JWT verification, OAuth helpers
│   │   └── main.py                 # FastAPI app entry point
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── conftest.py
│   ├── pyproject.toml
│   └── alembic/                    # DB migrations
│
├── specs/                          # SDD specifications
├── history/                        # PHRs and ADRs
├── .specify/                       # SpecKit Plus
├── CLAUDE.md
└── .env.example
```

## Data Model

### Core Entities

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│    User      │────<│  ToolConnection  │     │  Conversation  │>───┐
│─────────────│     │──────────────────│     │────────────────│    │
│ id (PK)      │     │ id (PK)          │     │ id (PK)        │    │
│ clerk_id     │     │ user_id (FK)     │     │ user_id (FK)   │    │
│ email        │     │ tool_type        │     │ title          │    │
│ display_name │     │ access_token ⊕   │     │ created_at     │    │
│ avatar_url   │     │ refresh_token ⊕  │     │ updated_at     │    │
│ created_at   │     │ token_expires_at │     │ is_archived    │    │
│ preferences  │     │ scopes           │     └────────────────┘    │
└─────────────┘     │ status           │                           │
                    │ metadata (JSONB) │     ┌────────────────┐    │
                    └──────────────────┘     │    Message      │<───┘
                                            │────────────────│
                                            │ id (PK)        │
                                            │ conversation_id│
                                            │ role           │  (user/assistant/system/tool)
                                            │ content        │
                                            │ tool_calls     │  (JSONB — agent metadata)
                                            │ created_at     │
                                            └────────────────┘

┌──────────────────┐     ┌────────────────┐
│  Notification    │     │    Skill       │
│──────────────────│     │────────────────│
│ id (PK)          │     │ id (PK)        │
│ user_id (FK)     │     │ name           │
│ source_tool      │     │ description    │
│ title            │     │ tool_type      │
│ content          │     │ template       │
│ priority         │     │ created_at     │
│ is_read          │     └────────────────┘
│ metadata (JSONB) │
│ created_at       │
└──────────────────┘

⊕ = encrypted at rest
```

## Agent Architecture

```
User Message
    │
    ▼
┌──────────────────────┐
│  Orchestrator Agent   │  ← Central router, intent classification
│  (OpenAI Agents SDK)  │
└──────┬───────────────┘
       │ handoff based on intent
       ├──────────────────┬──────────────────┬─────────────────┐
       ▼                  ▼                  ▼                 ▼
┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ EmailAgent  │  │  JiraAgent   │  │ SlackAgent   │  │ GitHubAgent  │
│ (Gmail MCP) │  │ (JIRA MCP)   │  │ (Slack MCP)  │  │ (GitHub MCP) │
└──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                │                  │                 │
       ▼                ▼                  ▼                 ▼
   MCP Server       MCP Server        MCP Server        MCP Server
   (stdio/Docker)   (stdio/Docker)    (stdio/Docker)    (stdio/Docker)
```

**Agent Loop**: Orchestrator → Sub-agent → MCP tool call → result → Sub-agent decides if done → loops or returns to Orchestrator. Loop breaks on task completion or user cancellation.

**SKILLS**: Before raw MCP calls, agents check for matching Skills (pre-built templates). Example: `summarize-unread-emails` SKILL reduces a 3-step MCP flow to a single optimized prompt.

**Confirmation Gate**: Any write/delete operation triggers a confirmation message back to the user before execution.

## API Contracts (Key Endpoints)

### Backend API (FastAPI)

| Method | Endpoint | Purpose |
|---|---|---|
| `POST` | `/api/chat` | Send message, receive SSE stream of agent response |
| `GET` | `/api/conversations` | List user's conversations |
| `GET` | `/api/conversations/:id` | Get full conversation with messages |
| `DELETE` | `/api/conversations/:id` | Delete a conversation |
| `GET` | `/api/tools` | List available tools & connection status |
| `POST` | `/api/tools/:type/connect` | Initiate OAuth2 flow for a tool |
| `GET` | `/api/tools/:type/callback` | OAuth2 callback handler |
| `DELETE` | `/api/tools/:type/disconnect` | Revoke and remove tool connection |
| `GET` | `/api/notifications` | List notifications from connected tools |
| `POST` | `/api/agents/confirm` | Confirm/cancel a pending write action |
| `GET` | `/api/ws/notifications` | WebSocket for real-time notifications |

### Frontend API Routes (Next.js BFF)

| Route | Purpose |
|---|---|
| `/api/clerk/webhook` | Clerk webhook for user sync |
| `/api/proxy/*` | Proxy to backend (adds Clerk JWT) |

## Phased Implementation Roadmap (14-16 weeks)

### Phase 1 — Foundation (Weeks 1-3)
- Project scaffolding (Next.js + FastAPI + Neon PostgreSQL)
- Clerk authentication (sign-up, login, protected routes)
- Database schema + Alembic migrations
- Three-panel dashboard shell (from Figma prototype)
- Dark/Light mode theme system

### Phase 2 — Tool Integration (Weeks 4-6)
- OAuth2 flow infrastructure (generic adapter pattern)
- First tool integration: **Gmail** (connect, read emails)
- MCP client manager (session lifecycle, tool discovery)
- Tool status UI (left panel — connected/disconnected badges)
- Second tool integration: **GitHub** (repos, issues, PRs)
- Third tool integration: **JIRA** (tickets, projects, boards)
- Fourth tool integration: **Slack** (channels, messages, notifications)
- Fifth tool integration: **Trello** (boards, lists, cards)
- Sixth tool integration: **Dropbox** (files, folders, sharing)
- Seventh tool integration: **Calendar** (events, scheduling, reminders)

### Phase 3 — AI Agent System (Weeks 7-9)
- Orchestrator agent with OpenAI Agents SDK + Gemini
- Single-tool agent execution (Gmail → summarize emails)
- SSE streaming for AI responses
- Chat persistence (conversations + messages in PostgreSQL)
- Chat history UI (left panel — new chat, switch, continue)

### Phase 4 — Multi-Agent & Activity (Weeks 10-12)
- Multi-agent handoffs (cross-tool operations)
- Confirmation gate for write/delete operations
- Right panel activity feed (notifications from connected tools)
- SKILLS system (pre-built templates for common operations)
- Additional tools: **JIRA**, **Slack**, **Trello**

### Phase 5 — Polish & Production (Weeks 13-16)
- Suggested actions & quick prompts
- Error handling, edge cases, token refresh
- Performance optimization
- Live deployment (Vercel + Railway)
- End-to-end testing

## Verification Plan

### Automated Tests
- Backend: `pytest` with async fixtures, test each API endpoint
- Frontend: `Vitest` + React Testing Library for component tests
- Integration: Test MCP tool calls with mock servers
- E2E: Playwright for critical user flows (sign-up → connect → chat)

### Manual Verification
- Live deployment on Vercel + Railway
- OAuth flows with real tool accounts
- Multi-agent cross-tool scenario testing
