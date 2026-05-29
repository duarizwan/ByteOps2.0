# Design: Help Center — ? Icon with Capability Popover

**Date:** 2026-05-29
**Status:** Approved

## Problem

New users don't know what they can ask ByteOps to do for each connected tool. When they ask something out of scope, the AI has no way to point them toward what is actually possible.

## Goal

A discoverable, lightweight help reference that shows per-tool capabilities without interrupting the chat flow. When out of scope, the AI can occasionally point users to it — but only when genuinely helpful.

## Design

### 1. ? Icon in chat header

A `HelpCircle` icon (lucide-react) added to the chat header in `chat-interface.tsx`, right-aligned next to the "ByteOps AI" title. Clicking it opens a Radix UI `Popover`.

### 2. Popover content

The popover renders only connected tools (sourced from `useToolConnections`). Each tool shows 4–5 plain-English capability lines. Example:

```
What can I help you with?

Gmail
  · Read and search your emails
  · Send, reply, or forward emails
  · Summarise inbox threads
  · Draft emails for your review

Slack
  · Read channels and messages
  · Send messages or DMs (with your confirmation)
  · Search conversations
  · List workspace users
```

If no tools are connected, the popover shows a single line: "Connect a tool in Settings → Connections to get started."

### 3. Static capability data

A new file `src/lib/tool-capabilities.ts` holds capability strings for all 7 supported tools (gmail, calendar, slack, jira, github, dropbox, trello). No API call required — data is static and mirrors what the backend agents already support.

### 4. Out-of-scope AI nudge

One instruction added to `RESPONSE_FORMAT` (the shared constant from the response-format feature):

> "If the user asks something clearly outside what you can do, you may occasionally mention the ? Help button at the top of the chat to see available capabilities. Do not say it every time — only when the user seems genuinely confused about scope."

No UI chips or special message components needed.

**Files changed:**
- `frontend/src/lib/tool-capabilities.ts` — new file, static capability data
- `frontend/src/components/dashboard/chat-interface.tsx` — add ? icon + popover
- `backend/app/agents/response_format.py` — add one line about the help icon

## Constraints

- Popover only shows currently connected tools (dynamic filter via `useToolConnections`).
- No new backend endpoints.
- Popover must work in both collapsed and expanded sidebar states.
- Must not obstruct the chat input or message area.

## Acceptance Criteria

- ? icon is visible in the chat header at all times.
- Clicking ? opens a popover listing capabilities for each connected tool.
- If no tools are connected, the popover shows a connect prompt.
- AI occasionally mentions the ? icon when a request is out of scope.
- AI does not mention the ? icon on every out-of-scope reply.
