# Workflow Tab: Delete Button + AI Suggestion Modal

**Date:** 2026-06-02  
**Branch:** 1-agent-runs-graph  
**Status:** Approved

---

## Overview

Two UI additions to the right-pane Workflow tab in the ByteOps dashboard (`context-panel.tsx`):

1. **Delete button** on each workflow card with inline two-click confirmation
2. **"Generate with AI" modal** accessible via a persistent button in the workflow tab content header, showing 5 pre-canned workflow suggestions

---

## Feature 1: Delete Workflow Button

### Placement
A red "Delete" button added to the end of each `WorkflowCard`'s action row, alongside the existing Pause/Resume, Run now, and Details buttons.

### Confirmation: Inline Two-Click
- **First click:** Button turns red and label changes to "Confirm delete?"
- **Second click:** Calls the DELETE API and removes the workflow
- **Anywhere else click / blur:** Resets back to "Delete" (cancels)
- No dialog or modal — entirely inline on the card

### API
Backend DELETE endpoint already exists: `DELETE /api/workflows/:id` (status 204).  
`use-workflows.ts` needs a new `deleteWorkflow(id: string)` function that calls this endpoint and removes the item from local state.

### Code changes
| File | Change |
|------|--------|
| `frontend/src/components/dashboard/context-panel.tsx` | Add `onDelete` prop to `WorkflowCard`, add `confirmDelete` local state (boolean), render conditional button label/style |
| `frontend/src/hooks/use-workflows.ts` | Add `deleteWorkflow(id)` function calling `DELETE /api/workflows/:id`, filter item from `workflows` state on success |

---

## Feature 2: "Generate with AI" Button + Suggestion Modal

### Persistent Button
A small `✦ Generate with AI` button rendered in the workflow content sub-header (above the card list), visible whether workflows exist or not — not only on the empty state.

Layout: `[2 Workflows (count label)]  [✦ Generate with AI →]`

### Suggestion Modal
A centered dialog that opens when the button is clicked. Shows 5 pre-canned workflow suggestion cards. Clicking a suggestion:
1. Calls `onSendToAI(suggestion.prompt)` to send the prompt to chat
2. Closes the modal

**5 suggestions (title + chat prompt):**

| Title | Prompt sent to chat |
|-------|---------------------|
| ☀️ Morning briefing | "Create a workflow that runs every morning, summarizes my Gmail and Slack messages, and lists anything urgent." |
| 📅 Meeting prep | "Create a workflow that runs before each calendar event to research the topic and prepare talking points." |
| 📊 Weekly status report | "Create a workflow that runs every Friday, summarizes my completed tasks, and drafts a team status update." |
| 🔔 Slack mention tracker | "Create a workflow that runs when Slack messages mention me, summarizes them, and adds action items to my task list." |
| 🌙 End-of-day wind-down | "Create a workflow that runs at 5pm every day, reviews my calendar for tomorrow, and sends a prep summary to my email." |

### Modal structure
- Header: "Choose a workflow to build" + subtitle "Pick one to get started — or describe your own in chat."
- Body: 5 suggestion cards (hover highlight, full click target)
- Footer: "Cancel" button (ghost style)
- Dismiss: clicking Cancel, pressing Escape, or clicking the backdrop

### Code changes
| File | Change |
|------|--------|
| `frontend/src/components/dashboard/context-panel.tsx` | Add `WorkflowSuggestionModal` component, add `showSuggestionModal` state, render persistent button above card list, wire modal open/close/select |

---

## Out of Scope
- Editing workflow names or actions from the panel
- Generating suggestions dynamically via AI (suggestions are static/pre-canned)
- Bulk delete

---

## Acceptance Criteria
- [ ] Delete button visible on every workflow card
- [ ] First click shows "Confirm delete?" in red; clicking elsewhere resets
- [ ] Second click calls DELETE API; card disappears from list
- [ ] "Generate with AI" button always visible in workflow tab (above card list)
- [ ] Clicking button opens modal with exactly 5 suggestions
- [ ] Clicking a suggestion sends its prompt to chat and closes modal
- [ ] Cancel / Escape / backdrop click closes modal without action
- [ ] Empty state is preserved when no workflows exist (button still shown above it)
- [ ] No regressions on Pause/Resume/Run now/Details buttons
