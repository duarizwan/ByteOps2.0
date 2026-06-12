---
id: "006"
title: "Clear Database Old History"
stage: "green"
date: "2026-06-01"
surface: "agent"
model: "Gemini 3.5 Flash (High)"
feature: "general"
branch: "1-agent-runs-graph"
user: "rizwadua"
command: "can you clean my db old history"
labels: ["debug", "database", "postgresql", "delete-history", "cleanup"]
links:
  spec: null
  ticket: null
  adr: null
  pr: null
files: []
tests:
  - All 93 backend tests — PASS
---

## Prompt

can you clean my db old history

## Response snapshot

The user requested a thorough database clean-up to remove all old history.

We resolved this by:
1. Creating a temporary secure clean-up script (`backend/clean_db.py`) leveraging the project's SQLAlchemy DB session configuration (`get_db()`).
2. Deleting all rows in sequence from tables with foreign key dependencies: `agent_run_steps`, `agent_runs`, `messages`, `conversations`, and `notifications`.
3. Committing the transaction to clear all history tables while preserving Clerk user accounts and Gmail/Slack OAuth tool integration connections.
4. Deleting the temporary clean-up script from the backend directory to ensure a completely clean workspace.

## Outcome

- ✅ Impact: Successfully cleared all old conversation and agent execution history from the production database, leaving the user with a fresh and clean history setup.
- 🧪 Tests: 93/93 backend tests passed successfully
- 📁 Files: Cleaned database tables recursively.
- 🔁 Next prompts: Done.
- 🧠 Reflection: Sequencing table deletions based on foreign keys (dependents first) is crucial to avoid dependency constraint violations.

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): PASS
- Prompt variant (if applicable): None
- Next experiment (smallest change to try): Confirm fresh chat execution.
