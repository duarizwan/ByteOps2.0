# Design: Alerts Tab — Unified Classifier

**Date**: 2026-05-29  
**Feature**: Right-panel Alerts tab relevance filtering  
**Status**: Approved  
**Scope**: `frontend/src/components/dashboard/context-panel.tsx` only

---

## Problem

The Alerts tab is currently a dumping ground: every notification that does not match `isTaskNotification()` lands there. There is no relevance gate. Low-signal informational items (build passed, email sent, PR merged by someone else) appear alongside genuine attention-needed alerts, creating noise and degrading the tab's signal value.

---

## Goal

Alerts shows only items that require the user's awareness. Everything else is silently discarded. Priority is classified precisely using backend metadata first, text signals as fallback.

---

## Architecture

### Before

```ts
const tasks  = notifications.filter(isTaskNotification);
const alerts = notifications.filter(n => !isTaskNotification(n)); // dumping ground
```

### After

```ts
type Classification = "task" | "alert" | "discard";
classifyNotification(n: Notification): Classification

const tasks  = notifications.filter(n => classifyNotification(n) === "task");
const alerts = notifications.filter(n => classifyNotification(n) === "alert");
// "discard" falls off silently — no UI, no count
```

---

## Decision Tree

`classifyNotification` evaluates in strict order. First match wins.

### 1. Task (checked first)

Backend metadata takes priority:
- `metadata.category` ∈ `["task", "action_item", "todo"]`
- `metadata.action_required === true`

Text fallback — precise action phrases only (existing `ACTION_WORDS` list):
- "action required", "asked you to", "assigned to you", "need you to", "needs your", "please review", "your approval", "waiting on you", "waiting for you", "follow up", "by friday", "by tomorrow", "todo", "to-do"

### 2. Alert (checked only if not a task)

Backend metadata signals (any one sufficient):
- `metadata.category` ∈ `["alert", "notification", "mention"]`
- `metadata.direct_mention === true`
- `metadata.auth_error === true`
- `metadata.token_expired === true`
- `metadata.build_failure === true`
- `metadata.deploy_failure === true`

Text signals — attention phrases only:
- `"failed"`, `"expired"`, `"error"`, `"overdue"`, `"deadline"`, `"mentioned you"`, `"requires your"`, `"needs review"`

Priority gate (last resort):
- Priority is `"high"` or `"urgent"` AND `content` is non-null and non-empty

### 3. Discard (default)

Everything not matched above. Silently dropped — no entry in Alerts, no badge count contribution.

---

## Priority Classification

Backend `extracted_priority` always wins if present and valid. Frontend inference is the fallback only.

| Tier | Frontend inference signals |
|---|---|
| `high` | `metadata.direct_mention`, `metadata.auth_error`, `metadata.token_expired`, `metadata.build_failure`, text contains `"overdue"/"deadline"/"expires"/"critical"` |
| `medium` | `metadata.assigned_to_you`, indirect mention signals, calendar-conflict signals, text contains `"important"/"attention"/"reminder"` |
| `low` | Passes alert gate but none of the above signals present |

---

## What Changes

| File | Change |
|---|---|
| `context-panel.tsx` | Replace `isTaskNotification` + alert derivation with `classifyNotification`. Refine `getNotificationPriority` to use tier table. Remove `HIGH_PRIORITY_WORDS` flat list. |
| `context-panel.test.tsx` | Update/extend tests to cover discard path and new priority tiers. |

**Nothing else changes.** No backend, no hooks, no new files, no component restructuring.

---

## What Stays the Same

- `NotificationCard` component — unchanged
- `TaskCard` component — unchanged
- `SyncStatusBar` — unchanged
- `cleanActivityText`, `getNotificationTitle` — unchanged
- Mark-all-read, Ask AI, dismiss — unchanged
- `ALERT_WORDS` list (existing text signals are reused, not replaced)

---

## Acceptance Criteria

1. A notification with `metadata.category: "info"` and `priority: "low"` does **not** appear in Alerts or Tasks.
2. A notification with `metadata.auth_error: true` appears in Alerts with priority `high`.
3. A notification with `metadata.category: "alert"` and `priority: "medium"` appears in Alerts with priority `medium`.
4. A notification with `metadata.action_required: true` appears in Tasks, not Alerts.
5. A notification with no metadata, `priority: "low"`, and no matching text is silently discarded.
6. Backend `extracted_priority: "medium"` overrides frontend-inferred `high`.
7. All existing tests pass; new tests cover discard and priority-tier paths.

---

## Non-Goals

- No backend changes.
- No new UI components or layout changes.
- No changes to the Tasks tab logic (it stays as-is).
- No changes to the Workflows tab.
