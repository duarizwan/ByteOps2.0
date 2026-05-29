# Design: Shared Response Format for AI Agents

**Date:** 2026-05-29
**Status:** Approved

## Problem

All ByteOps AI agents instruct themselves to "format responses in clean Markdown," producing output heavy with `###` headers, `**bold**`, `---` dividers, and bullet points even for short conversational replies. This looks AI-generated and unattractive in the chat UI.

## Goal

Users receive plain, natural prose — like a helpful colleague in a chat — without decorative markdown clutter. Structured data (tables of issues, file listings, events) stays readable but decorative formatting is eliminated.

## Design

### Shared constant

A new file `backend/app/agents/response_format.py` exports one string constant `RESPONSE_FORMAT`:

```
Response style — follow strictly:
- Write in plain, natural prose. Like a helpful colleague in a chat, not a document.
- No headers (###, ##, #). Ever.
- No bold (**text**) or italic (*text**) for decoration or emphasis.
- No horizontal rules (---).
- Use a numbered list only when steps must be done in a specific order (3+ steps).
- Use a plain bullet list only when there are 4+ genuinely parallel items that read awkwardly as prose.
- For structured data only (issue lists, file listings, calendar events), a minimal plain table is allowed.
- One clear sentence beats three padded ones. Keep it short.
```

### Injection into agents

Every agent appends `RESPONSE_FORMAT` to its system prompt. The current "Format all responses in clean Markdown" line in each of the 6 specialist prompts is replaced with `+ RESPONSE_FORMAT`. The orchestrator's `# Response formatting` block inside `build_system_prompt()` is replaced with `{RESPONSE_FORMAT}`.

**Files changed:**
- `backend/app/agents/response_format.py` — new file
- `backend/app/agents/orchestrator.py` — replace formatting block
- `backend/app/agents/gmail_agent.py` — replace formatting line
- `backend/app/agents/calendar_agent.py` — replace formatting line
- `backend/app/agents/github_agent.py` — replace formatting line
- `backend/app/agents/slack_agent.py` — replace formatting line
- `backend/app/agents/jira_agent.py` — replace formatting line (keep table allowance for issue lists)
- `backend/app/agents/dropbox_agent.py` — replace formatting line (keep table allowance for file listings)

## Constraints

- Tables remain allowed for Jira issue lists and Dropbox file listings — structured data genuinely benefits from tabular layout.
- No frontend changes.
- No new API endpoints.

## Acceptance Criteria

- AI responses use prose sentences for short replies (no headers, bold, or dividers).
- Jira issue lists and Dropbox file listings still render as tables.
- Numbered lists appear only for sequential steps.
- All 7 agents share the same format rule from a single source.
