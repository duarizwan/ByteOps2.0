# Connect Tool via API Key — Design Spec

**Date:** 2026-06-02
**Branch:** 1-agent-runs-graph
**Status:** Approved for implementation

---

## Summary

Extend the "Connect New Tool" modal in the CollapsibleSidebar with a two-tab layout:
- **API Key tab (default):** User picks a platform chip, fills in the required credentials, hits Connect. No OAuth redirect needed.
- **OAuth tab:** The existing `ConnectToolModal` tool list, unchanged.

Gmail and Google Calendar are OAuth-only and are not included in the API Key tab (Google does not issue simple API tokens for these services). Their chips appear dimmed with an asterisk; clicking them redirects the user to the OAuth tab.

---

## In Scope

- Frontend: redesigned `ConnectToolModal` with two tabs
- Frontend: per-tool credential forms (GitHub, Jira, Slack, Trello, Dropbox)
- Backend: new `POST /api/auth/{tool}/connect-apikey` endpoint per supported tool
- Backend: credential validation before storage (one test API call)
- Backend: encrypted storage of API key credentials (same store as OAuth tokens)
- Error handling: invalid/insufficient-scope credentials surfaced in the form

## Out of Scope

- Adding new tools beyond the existing 7
- "Bring your own tool" / arbitrary custom integrations
- Token refresh logic (API keys don't expire the way OAuth tokens do)
- Changes to the Settings page tool grid (`/settings`)

---

## Supported Tools & Required Fields

| Tool | Fields | Notes |
|------|--------|-------|
| GitHub | Personal Access Token | Needs scopes: `repo`, `read:org`, `read:user` |
| Jira | Workspace URL, Email, API Token | Workspace = `yourcompany.atlassian.net` |
| Slack | Bot Token | Format: `xoxb-...` |
| Trello | API Key + API Token | Both from trello.com/app-key |
| Dropbox | Access Token | Format: `sl....` |
| Gmail | — | OAuth only. Chip shown dimmed; clicking redirects to OAuth tab |
| Google Calendar | — | OAuth only. Same behaviour as Gmail |

---

## Architecture

### Frontend

**File:** `frontend/src/components/dashboard/collapsible-sidebar.tsx`

Replace the existing `ConnectToolModal` component (lines ~257–402) with an updated version containing:

1. **Tab bar** — "API Key" (default) | "OAuth (existing)"
2. **API Key panel:**
   - Tool chip selector (7 chips; Gmail/Calendar dimmed)
   - Dynamic form area — swaps fields based on selected chip
   - Per-tool field definitions (label, placeholder, hint, required scopes note)
   - "Connect" button — disabled until required fields are filled
   - On submit: calls `POST /api/auth/{tool}/connect-apikey` with credentials
   - Shows inline error on failure (invalid token, wrong scopes, network error)
   - Shows success state then closes modal on success
3. **OAuth panel:** existing tool list rendered as-is (no changes to OAuth flow)

**New hook method:** `connectViaApiKey(tool: ToolType, credentials: Record<string, string>)` added to `useToolConnections` hook.

### Backend

**New endpoint per tool:** `POST /api/auth/{tool}/connect-apikey`

```
Request body:  { credentials: { [field]: string } }
Auth:          Bearer JWT (Clerk)
Response 200:  { status: "connected", tool_type: string }
Response 400:  { error: "invalid_credentials", message: string }
Response 422:  { error: "insufficient_scopes", message: string, required: string[] }
```

**Handler flow:**
1. Validate request body — required fields present and non-empty
2. Make a lightweight test API call to the tool using the provided credentials
   - GitHub: `GET /user` 
   - Jira: `GET /rest/api/3/myself`
   - Slack: `auth.test`
   - Trello: `GET /1/members/me`
   - Dropbox: `POST /2/users/get_current_account`
3. If call fails → return 400 with error message
4. Check returned scopes/permissions match minimum required → return 422 if insufficient
5. Encrypt credentials and store in the same `tool_connections` table, with `auth_method: "apikey"`
6. Return 200

**Database:** The existing `tool_connections` table likely needs one new column: `auth_method VARCHAR DEFAULT 'oauth'`. This distinguishes API key connections from OAuth ones so refresh logic can skip API key connections. If token/credential data is already stored as JSON, no other schema changes are needed. Verify against current schema before implementation.

---

## Data Flow

```
User fills form → click Connect
  → frontend validates fields non-empty
  → POST /api/auth/{tool}/connect-apikey  { credentials }
    → backend validates
    → test API call to tool
    → store encrypted credentials
    → return { status: "connected" }
  → frontend: mark tool as connected in useToolConnections state
  → modal closes (or shows success tick then closes after 1s)
```

---

## Error Handling

| Scenario | Frontend behaviour |
|----------|--------------------|
| Field left empty | Connect button stays disabled |
| Invalid token (401 from tool) | Inline red error under field: "Invalid token — check and try again" |
| Insufficient scopes (403) | Inline amber warning: "Token connected but missing scopes: repo, read:org. Reconnect with correct permissions." |
| Network / backend down | Toast error: "Could not reach ByteOps. Check connection and retry." |
| Tool already connected | Warn in modal: "Already connected via OAuth. Connecting via API key will replace it." |

---

## Component Structure

```
ConnectToolModal (updated)
├── TabBar  [API Key | OAuth]
├── ApiKeyPanel
│   ├── ToolChipSelector
│   │   └── ToolChip × 7  (Gmail/Calendar dimmed)
│   └── ToolCredentialForm  (switches per selected chip)
│       ├── ScopesNote
│       ├── FormField × N  (varies per tool)
│       ├── FieldHint (with docs link)
│       └── ConnectButton
└── OAuthPanel  (existing ConnectToolModal content, unchanged)
```

---

## Testing

- Unit: `ConnectToolModal` renders API Key tab by default
- Unit: Chip selection swaps form fields correctly
- Unit: Connect button disabled when required fields empty
- Unit: Inline error shown on 400 response
- Integration: `POST /api/auth/github/connect-apikey` with valid PAT → stored + 200
- Integration: Invalid PAT → 400 with message
- Integration: Insufficient scopes → 422 with required scopes list
- E2E (manual): Full connect flow for GitHub PAT, verify tool shows Connected in sidebar

---

## Follow-ups / Risks

1. **Trello already uses a non-standard OAuth callback** (`/trello-callback`) — verify API key auth path doesn't conflict with the existing callback handler.
2. **Token storage encryption** — confirm the existing OAuth token encryption is reusable for API keys without schema changes.
3. **Scope validation complexity** — Slack and Trello scope models differ from GitHub/Jira; may need tool-specific scope-checking logic in the backend.
