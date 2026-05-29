# ByteOps Platform Constitution

## Core Principles

### I. AI-First Middleware
ByteOps is a centralized AI-powered productivity platform that acts as intelligent middleware between users and their business tools (Gmail, Slack, JIRA, GitHub, Trello, Dropbox, Calendar, etc.).
- The AI Assistant is the **primary interaction surface** — users interact via natural language.
- All tool interactions flow through **MCP (Model Context Protocol) servers** — no custom API wrappers.
- The AI can **read, write, and execute actions** across all connected tools, but **requires explicit user confirmation** before any write/delete operation.
- Adding new tools must be trivial — **modular MCP adapter pattern** so connecting a new service is plug-and-play.

### II. Multi-Agent Architecture
The AI system uses a **hierarchical agent architecture**:
- **Central Orchestrator Agent**: Routes user intent to the correct specialized agent.
- **Specialized Tool Agents**: One per tool domain (EmailAgent, JiraAgent, SlackAgent, etc.) with sub-agents for complex multi-step tasks.
- **SKILLS System**: Pre-built prompt templates for common operations to reduce token usage and MCP call costs.
- Agent handoffs via **OpenAI Agents SDK** patterns.

### III. Three-Panel Dashboard
The UI is a stable, resizable three-panel layout — the user's single pane of glass:
- **Left Panel**: Connected tools (with status badges + notification counts), quick-access settings, chat history, "New Chat" button.
- **Middle Panel**: AI chat interface — the primary interaction surface. Streaming responses, suggested prompts, file attachments.
- **Right Panel**: Contextual activity feed — Workflows, Alerts, Tasks tabs. Surfaces important notifications from integrated tools proactively.
- Dark mode supported from day one.
- Mobile responsiveness deferred until 80% feature completion.

### IV. Test-First Development (NON-NEGOTIABLE)
- TDD mandatory: Red → Green → Refactor strictly enforced.
- Every feature starts with `specs/<feature>/spec.md`.
- Minimum 80% test coverage for core business logic.
- All changes must be small, testable, and reference code precisely.

### V. Security by Design
- **Clerk** for user authentication (Email/Password, Google Sign-In, GitHub Sign-In).
- **OAuth2** for all tool integrations — per-user, never shared across accounts.
- No hardcoded credentials — `.env` and secrets management only.
- Principle of least privilege for all service permissions.
- Multi-user platform — each user has isolated tool connections and data.

### VI. Production-Grade Quality
This is **not a prototype**. ByteOps is being built as a full production web application.
- Persistent chat history, user data, cached tool data, workflow definitions — all stored in PostgreSQL.
- Deployment to live web hosting (free tier: Vercel + Neon + Railway/Render).
- Industry-standard error handling, logging, and observability.
- Start simple, build incrementally — YAGNI. But never cut corners on architecture.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15 (App Router, TypeScript, Tailwind CSS) |
| Backend | Python 3.10+ (managed via `uv`, FastAPI) |
| AI Orchestration | OpenAI Agents SDK |
| LLM Provider | Google Gemini API |
| Tool Integration | MCP servers (stdio/Docker-based) |
| Database | PostgreSQL (Neon — cloud-hosted) |
| Authentication | Clerk (Email/Password, Google, GitHub) |
| Real-time | SSE for AI streaming, WebSockets for live notifications |
| Testing | `pytest` (Backend), `Vitest` (Frontend) |
| Deployment | Vercel (frontend) + Railway/Render (backend, free tier) |

### Repository Structure (Monorepo)
```
ByteOps/
├── frontend/          # Next.js application
├── backend/           # Python FastAPI + Agents
├── specs/             # SDD feature specifications
├── history/           # PHRs and ADRs
├── .specify/          # SpecKit Plus templates/scripts
├── CLAUDE.md          # Agent rules
└── .env.example       # Environment variable template
```

### Prohibited Practices
- No hardcoded credentials or API keys.
- No direct database access from UI components.
- No untested code in main branch.
- No custom API wrappers when an MCP server exists.
- No assumptions from internal knowledge — verify externally.

## Development Workflow

1. **Constitution** → Project principles (this document).
2. **Specify** → `specs/<feature>/spec.md` with acceptance criteria.
3. **Plan** → Architecture in `specs/<feature>/plan.md`.
4. **Tasks** → Testable atomic tasks in `specs/<feature>/tasks.md`.
5. **Implement** → Red → Green → Refactor.
6. **Record** → PHRs after every prompt; ADRs for significant decisions.

## Governance

- This constitution supersedes all other development practices.
- Amendments require documentation, approval, and a migration plan.
- All code changes must verify compliance with these principles.
- Complexity must be justified; default to simplicity.

**Version**: 2.0.0 | **Ratified**: 2026-02-24 | **Last Amended**: 2026-02-24
