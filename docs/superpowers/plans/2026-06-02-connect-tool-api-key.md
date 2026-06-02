# Connect Tool via API Key — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-tab "Connect a Tool" modal — "API Key" tab (new, default) lets users paste credentials directly for GitHub/Jira/Slack/Trello/Dropbox; "OAuth" tab shows the existing tool list unchanged.

**Architecture:** Backend gets a new `POST /api/auth/{tool}/connect-apikey` endpoint in `oauth.py` that validates credentials with a test API call then upserts the `ToolConnection` row. Frontend replaces the `ConnectToolModal` body with a tabbed component; a new `connectViaApiKey` method is added to `useToolConnections`. No DB schema changes — `metadata_` JSONB column stores `auth_method: "apikey"` plus any extra fields (Jira workspace, Trello api_key).

**Tech Stack:** FastAPI + SQLAlchemy (backend), Next.js + React + Tailwind + Lucide + brand-icons.tsx (frontend), Vitest + React Testing Library (frontend tests), pytest + httpx (backend tests).

---

### Task 1: Backend — `connect-apikey` endpoint

**Files:**
- Modify: `backend/app/api/oauth.py`
- Test: `backend/tests/test_oauth.py`

- [ ] **Step 1: Write the failing backend tests**

Add to `backend/tests/test_oauth.py` after the existing imports and helpers:

```python
# ── API Key connection tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_apikey_github_valid():
    """Valid GitHub PAT → 200 connected."""
    from app.core.auth import get_current_clerk_user
    from app.core.database import get_db

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=lambda: None))
    mock_db.add = AsyncMock()
    mock_db.commit = AsyncMock()

    mock_gh_response = AsyncMock()
    mock_gh_response.status_code = 200

    with (
        patch("app.api.oauth.get_current_clerk_user", return_value=MOCK_USER),
        patch("app.api.oauth.get_db", return_value=mock_db),
        patch("httpx.AsyncClient.get", return_value=mock_gh_response),
        patch("app.api.oauth.trigger_immediate_sync"),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/github/connect-apikey",
                json={"credentials": {"token": "ghp_validtoken"}},
                headers={"Authorization": "Bearer fake"},
            )
    assert resp.status_code == 200
    assert resp.json()["status"] == "connected"


@pytest.mark.asyncio
async def test_connect_apikey_github_invalid_token():
    """Invalid GitHub PAT → 400."""
    mock_db = AsyncMock()

    mock_gh_response = AsyncMock()
    mock_gh_response.status_code = 401

    with (
        patch("app.api.oauth.get_current_clerk_user", return_value=MOCK_USER),
        patch("app.api.oauth.get_db", return_value=mock_db),
        patch("httpx.AsyncClient.get", return_value=mock_gh_response),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/github/connect-apikey",
                json={"credentials": {"token": "bad"}},
                headers={"Authorization": "Bearer fake"},
            )
    assert resp.status_code == 400
    assert "Invalid GitHub token" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_connect_apikey_gmail_rejected():
    """Gmail is OAuth-only → 400."""
    with patch("app.api.oauth.get_current_clerk_user", return_value=MOCK_USER):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/gmail/connect-apikey",
                json={"credentials": {"token": "x"}},
                headers={"Authorization": "Bearer fake"},
            )
    assert resp.status_code == 400
    assert "OAuth" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_connect_apikey_jira_missing_fields():
    """Jira with missing workspace → 400."""
    mock_db = AsyncMock()
    with (
        patch("app.api.oauth.get_current_clerk_user", return_value=MOCK_USER),
        patch("app.api.oauth.get_db", return_value=mock_db),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/api/auth/jira/connect-apikey",
                json={"credentials": {"email": "a@b.com", "token": "tok"}},
                headers={"Authorization": "Bearer fake"},
            )
    assert resp.status_code == 400
    assert "workspace" in resp.json()["detail"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/test_oauth.py::test_connect_apikey_github_valid tests/test_oauth.py::test_connect_apikey_github_invalid_token tests/test_oauth.py::test_connect_apikey_gmail_rejected tests/test_oauth.py::test_connect_apikey_jira_missing_fields -v
```

Expected: 4 FAILED — `404 Not Found` (endpoint doesn't exist yet).

- [ ] **Step 3: Add the endpoint to `backend/app/api/oauth.py`**

Add after the existing imports at the top of `oauth.py`:

```python
from pydantic import BaseModel

class ApiKeyCredentials(BaseModel):
    credentials: dict[str, str]
```

Add these three functions and one route **before** the `disconnect_tool` route at the bottom of `oauth.py`:

```python
# ──────────────────────────────────────────────────────────────────────────────
# API Key connection — validate credentials then upsert ToolConnection
# ──────────────────────────────────────────────────────────────────────────────

_APIKEY_SUPPORTED = {ToolType.GITHUB, ToolType.JIRA, ToolType.SLACK, ToolType.TRELLO, ToolType.DROPBOX}


async def _validate_apikey_credentials(tool: ToolType, creds: dict[str, str]) -> None:
    """Make a lightweight test call to confirm credentials are valid. Raises HTTPException on failure."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        if tool == ToolType.GITHUB:
            token = creds.get("token", "")
            if not token:
                raise HTTPException(status_code=400, detail="token is required")
            resp = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {token}", "Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid GitHub token")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"GitHub API error: {resp.status_code}")

        elif tool == ToolType.JIRA:
            workspace = creds.get("workspace", "").strip().rstrip("/")
            email = creds.get("email", "")
            token = creds.get("token", "")
            if not workspace:
                raise HTTPException(status_code=400, detail="workspace is required")
            if not email or not token:
                raise HTTPException(status_code=400, detail="email and token are required")
            import base64 as _b64
            auth = _b64.b64encode(f"{email}:{token}".encode()).decode()
            resp = await client.get(
                f"https://{workspace}/rest/api/3/myself",
                headers={"Authorization": f"Basic {auth}", "Accept": "application/json"},
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Jira credentials — check email and token")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Jira API error: {resp.status_code}")

        elif tool == ToolType.SLACK:
            token = creds.get("token", "")
            if not token:
                raise HTTPException(status_code=400, detail="token is required")
            resp = await client.post(
                "https://slack.com/api/auth.test",
                headers={"Authorization": f"Bearer {token}"},
            )
            data = resp.json()
            if not data.get("ok"):
                raise HTTPException(status_code=400, detail=f"Invalid Slack token: {data.get('error', 'unknown')}")

        elif tool == ToolType.TRELLO:
            api_key = creds.get("api_key", "")
            token = creds.get("token", "")
            if not api_key or not token:
                raise HTTPException(status_code=400, detail="api_key and token are required")
            resp = await client.get(
                f"https://api.trello.com/1/members/me?key={api_key}&token={token}",
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Trello credentials")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Trello API error: {resp.status_code}")

        elif tool == ToolType.DROPBOX:
            token = creds.get("token", "")
            if not token:
                raise HTTPException(status_code=400, detail="token is required")
            resp = await client.post(
                "https://api.dropboxapi.com/2/users/get_current_account",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                content=b"null",
            )
            if resp.status_code == 401:
                raise HTTPException(status_code=400, detail="Invalid Dropbox token")
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail=f"Dropbox API error: {resp.status_code}")


def _extract_token_and_metadata(tool: ToolType, creds: dict[str, str]) -> tuple[str, dict]:
    """Return (access_token_to_store, metadata_dict) from raw credentials."""
    if tool == ToolType.JIRA:
        return creds["token"], {
            "auth_method": "apikey",
            "workspace": creds["workspace"].strip().rstrip("/"),
            "email": creds["email"],
        }
    if tool == ToolType.TRELLO:
        return creds["token"], {"auth_method": "apikey", "api_key": creds["api_key"]}
    return creds["token"], {"auth_method": "apikey"}


@router.post("/{tool}/connect-apikey")
async def connect_tool_apikey(
    tool: ToolType,
    body: ApiKeyCredentials,
    current_user: Annotated[User, Depends(get_current_clerk_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    background_tasks: BackgroundTasks,
) -> dict:
    """Connect a tool using a user-supplied API key / personal access token."""
    if tool not in _APIKEY_SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail=f"{tool} does not support API key auth. Use OAuth.",
        )

    await _validate_apikey_credentials(tool, body.credentials)
    access_token, metadata = _extract_token_and_metadata(tool, body.credentials)

    existing = await db.execute(
        select(ToolConnection).where(
            ToolConnection.user_id == current_user.id,
            ToolConnection.tool_type == tool,
        )
    )
    connection = existing.scalar_one_or_none()
    now = datetime.now(timezone.utc)

    if connection:
        connection.access_token = access_token
        connection.refresh_token = None
        connection.token_expires_at = None
        connection.scopes = None
        connection.status = ConnectionStatus.CONNECTED
        connection.updated_at = now
        connection.metadata_ = metadata
    else:
        connection = ToolConnection(
            user_id=current_user.id,
            tool_type=tool,
            access_token=access_token,
            refresh_token=None,
            token_expires_at=None,
            scopes=None,
            status=ConnectionStatus.CONNECTED,
            metadata_=metadata,
        )
        db.add(connection)

    await db.commit()

    from app.services.sync.scheduler import trigger_immediate_sync
    background_tasks.add_task(trigger_immediate_sync, user_id=current_user.id, tool_type=tool)

    return {"status": "connected", "tool_type": tool}
```

- [ ] **Step 4: Run the tests — expect 4 PASS**

```bash
cd backend && python -m pytest tests/test_oauth.py::test_connect_apikey_github_valid tests/test_oauth.py::test_connect_apikey_github_invalid_token tests/test_oauth.py::test_connect_apikey_gmail_rejected tests/test_oauth.py::test_connect_apikey_jira_missing_fields -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Run the full oauth test suite to check no regressions**

```bash
cd backend && python -m pytest tests/test_oauth.py -v
```

Expected: all previously passing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/api/oauth.py backend/tests/test_oauth.py
git commit -m "feat: add connect-apikey endpoint for GitHub, Jira, Slack, Trello, Dropbox"
```

---

### Task 2: Hook — `connectViaApiKey` method

**Files:**
- Modify: `frontend/src/hooks/use-tool-connections.ts`
- Test: `frontend/tests/tool-connections.test.tsx`

- [ ] **Step 1: Write the failing frontend hook test**

Read `frontend/tests/tool-connections.test.tsx` to see existing test structure, then append:

```typescript
// Add to the existing describe block or create new describe block:
describe("connectViaApiKey", () => {
    it("calls connect-apikey endpoint and refreshes connections on success", async () => {
        const mockGetToken = vi.fn().mockResolvedValue("mock-token");
        vi.mocked(useAuth).mockReturnValue({ getToken: mockGetToken } as any);

        global.fetch = vi.fn()
            .mockResolvedValueOnce({
                ok: true,
                json: async () => ({ status: "connected", tool_type: "github" }),
            } as Response)
            .mockResolvedValueOnce({
                ok: true,
                json: async () => [],
            } as Response); // fetchConnections after success

        const { result } = renderHook(() => useToolConnections());
        await act(async () => {
            await result.current.connectViaApiKey("github", { token: "ghp_test" });
        });

        expect(global.fetch).toHaveBeenCalledWith(
            expect.stringContaining("/api/auth/github/connect-apikey"),
            expect.objectContaining({
                method: "POST",
                headers: expect.objectContaining({ Authorization: "Bearer mock-token" }),
                body: JSON.stringify({ credentials: { token: "ghp_test" } }),
            })
        );
    });

    it("throws when connect-apikey returns non-ok response", async () => {
        const mockGetToken = vi.fn().mockResolvedValue("mock-token");
        vi.mocked(useAuth).mockReturnValue({ getToken: mockGetToken } as any);

        global.fetch = vi.fn().mockResolvedValueOnce({
            ok: false,
            json: async () => ({ detail: "Invalid GitHub token" }),
        } as Response);

        const { result } = renderHook(() => useToolConnections());
        await expect(
            act(async () => {
                await result.current.connectViaApiKey("github", { token: "bad" });
            })
        ).rejects.toThrow("Invalid GitHub token");
    });
});
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd frontend && npx vitest run tests/tool-connections.test.tsx
```

Expected: FAIL — `connectViaApiKey is not a function`.

- [ ] **Step 3: Add `connectViaApiKey` to `use-tool-connections.ts`**

Add this method inside `useToolConnections()`, after the existing `disconnect` callback and before `isConnected`:

```typescript
const connectViaApiKey = useCallback(
    async (tool: ToolType, credentials: Record<string, string>) => {
        const token = await getToken();
        if (!token) throw new Error("You must be signed in to connect tools");
        const res = await fetch(`${API_BASE}/api/auth/${tool}/connect-apikey`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                Authorization: `Bearer ${token}`,
            },
            body: JSON.stringify({ credentials }),
        });
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail ?? `Failed to connect ${tool}`);
        }
        await fetchConnections();
    },
    [getToken, fetchConnections]
);
```

Also add `connectViaApiKey` to the return object at the bottom of the hook:

```typescript
return { connections, loading, error, isConnected, initiateConnect, disconnect, silentRefresh, refetch: fetchConnections, connectViaApiKey };
```

- [ ] **Step 4: Run to verify it passes**

```bash
cd frontend && npx vitest run tests/tool-connections.test.tsx
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/use-tool-connections.ts frontend/tests/tool-connections.test.tsx
git commit -m "feat: add connectViaApiKey method to useToolConnections hook"
```

---

### Task 3: Frontend — tabbed `ConnectToolModal`

**Files:**
- Modify: `frontend/src/components/dashboard/collapsible-sidebar.tsx`
- Test: `frontend/tests/collapsible-sidebar.test.tsx`

- [ ] **Step 1: Write the failing frontend tests**

First, update `frontend/tests/collapsible-sidebar.test.tsx`:

1. Change the existing `import { render }` line to also import `fireEvent` and `screen`:
```typescript
import { fireEvent, render, screen } from "@testing-library/react";
```

2. Replace the existing `vi.mock("@/hooks/use-tool-connections", ...)` call (only one mock per module allowed) with the updated version that includes all methods:
```typescript
vi.mock("@/hooks/use-tool-connections", () => ({
    useToolConnections: () => ({
        isConnected: (id: string) => id === "gmail",
        initiateConnect: vi.fn(),
        disconnect: vi.fn(),
        connectViaApiKey: vi.fn(),
    }),
}));
```

3. Append the new describe block at the end of the file:

describe("ConnectToolModal", () => {
    it("opens modal with API Key tab active by default", async () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        // Find and click the Connect New Tool button
        const btn = container.querySelector("button[data-testid='connect-new-tool-btn']")
            ?? Array.from(container.querySelectorAll("button")).find(b => b.textContent?.includes("Connect New Tool"));
        expect(btn).toBeTruthy();
        fireEvent.click(btn!);
        expect(screen.getByText("API Key")).toBeTruthy();
        expect(screen.getByText("OAuth")).toBeTruthy();
    });

    it("shows per-tool fields when GitHub chip is selected", async () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const btn = Array.from(container.querySelectorAll("button")).find(b => b.textContent?.includes("Connect New Tool"));
        fireEvent.click(btn!);
        const githubChip = screen.getByText("GitHub");
        fireEvent.click(githubChip);
        expect(screen.getByPlaceholderText(/ghp_/)).toBeTruthy();
    });

    it("shows OAuth tab content when OAuth tab is clicked", async () => {
        const { container } = render(<CollapsibleSidebar {...baseProps} />);
        const btn = Array.from(container.querySelectorAll("button")).find(b => b.textContent?.includes("Connect New Tool"));
        fireEvent.click(btn!);
        const oauthTab = screen.getByText("OAuth");
        fireEvent.click(oauthTab);
        expect(screen.getByText("Select a tool to connect via OAuth")).toBeTruthy();
    });
});
```

- [ ] **Step 2: Run to verify tests fail**

```bash
cd frontend && npx vitest run tests/collapsible-sidebar.test.tsx
```

Expected: the new tests FAIL (modal doesn't have tabs yet).

- [ ] **Step 3: Add the tool config constant to `collapsible-sidebar.tsx`**

Add this constant block after the `TOOL_REGISTRY` definition (after line 39):

```typescript
/* ========================
   API Key tool config — fields required per tool
   ======================== */
const OAUTH_ONLY_TOOLS = new Set<ToolType>(["gmail", "calendar"]);

interface ApiKeyField {
    key: string;
    label: string;
    placeholder: string;
    type: "text" | "password";
}
interface ApiKeyToolConfig {
    fields: ApiKeyField[];
    hint: string;
    scopes: string;
}

const API_KEY_TOOL_CONFIG: Partial<Record<ToolType, ApiKeyToolConfig>> = {
    github: {
        fields: [{ key: "token", label: "Personal Access Token", placeholder: "ghp_xxxxxxxxxxxxxxxxxxxx", type: "password" }],
        hint: "Generate at github.com → Settings → Developer settings → Personal access tokens",
        scopes: "repo, read:org, read:user",
    },
    jira: {
        fields: [
            { key: "workspace", label: "Workspace URL", placeholder: "yourcompany.atlassian.net", type: "text" },
            { key: "email", label: "Email Address", placeholder: "you@company.com", type: "text" },
            { key: "token", label: "API Token", placeholder: "ATATxxxxxxxxxxxxxxxxxxxxxxxx", type: "password" },
        ],
        hint: "Generate at id.atlassian.com → Security → API tokens",
        scopes: "read:jira-work, write:jira-work",
    },
    slack: {
        fields: [{ key: "token", label: "Bot Token", placeholder: "xoxb-xxxxxxxxxxxx-xxxxxxxxxxxx", type: "password" }],
        hint: "From your Slack App → OAuth & Permissions → Bot User OAuth Token",
        scopes: "channels:read, chat:write, users:read",
    },
    trello: {
        fields: [
            { key: "api_key", label: "API Key", placeholder: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", type: "text" },
            { key: "token", label: "API Token", placeholder: "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", type: "password" },
        ],
        hint: "Get both at trello.com/app-key",
        scopes: "read, write",
    },
    dropbox: {
        fields: [{ key: "token", label: "Access Token", placeholder: "sl.xxxxxxxxxxxxxxxxxxxxxxxxxx", type: "password" }],
        hint: "Generate at dropbox.com/developers/apps → your app → OAuth 2 → Generated access token",
        scopes: "files.content.read, files.metadata.read",
    },
};
```

- [ ] **Step 4: Replace the `ConnectToolModal` component**

Replace the entire `ConnectToolModal` function (from `function ConnectToolModal` on line 257 through the closing `}` on line 402) with:

```typescript
function ConnectToolModal({ onClose }: { onClose: () => void }) {
    const { isConnected, initiateConnect, disconnect, connectViaApiKey } = useToolConnections();
    const [activeTab, setActiveTab] = useState<"apikey" | "oauth">("apikey");
    const [selectedTool, setSelectedTool] = useState<ToolType>("github");
    const [credentials, setCredentials] = useState<Record<string, string>>({});
    const [connecting, setConnecting] = useState(false);
    const [oauthBusy, setOauthBusy] = useState<ToolType | null>(null);
    const [disconnecting, setDisconnecting] = useState<ToolType | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [successTool, setSuccessTool] = useState<ToolType | null>(null);
    const overlayRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [onClose]);

    // Reset credentials when tool changes
    const handleSelectTool = (toolId: ToolType) => {
        if (OAUTH_ONLY_TOOLS.has(toolId)) {
            setActiveTab("oauth");
            return;
        }
        setSelectedTool(toolId);
        setCredentials({});
        setError(null);
    };

    const handleApiKeyConnect = async () => {
        setError(null);
        setConnecting(true);
        try {
            await connectViaApiKey(selectedTool, credentials);
            setSuccessTool(selectedTool);
            setTimeout(onClose, 1200);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to connect ${selectedTool}`);
        } finally {
            setConnecting(false);
        }
    };

    const handleOAuthConnect = async (toolId: ToolType) => {
        setError(null);
        setOauthBusy(toolId);
        try {
            await initiateConnect(toolId);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to connect ${toolId}`);
        } finally {
            setOauthBusy(null);
        }
    };

    const handleDisconnect = async (toolId: ToolType) => {
        setError(null);
        setDisconnecting(toolId);
        try {
            await disconnect(toolId);
        } catch (err) {
            setError(err instanceof Error ? err.message : `Failed to disconnect ${toolId}`);
        } finally {
            setDisconnecting(null);
        }
    };

    const config = API_KEY_TOOL_CONFIG[selectedTool];
    const allFieldsFilled = config
        ? config.fields.every((f) => (credentials[f.key] ?? "").trim().length > 0)
        : false;

    return (
        <div
            ref={overlayRef}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={(e) => { if (e.target === overlayRef.current) onClose(); }}
        >
            <div className="w-full max-w-sm mx-4 bg-card border border-border rounded-2xl shadow-2xl flex flex-col overflow-hidden">
                {/* Header */}
                <div className="flex items-center justify-between px-5 py-4 border-b border-border">
                    <div>
                        <h2 className="font-semibold text-foreground text-base">Connect a Tool</h2>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {activeTab === "apikey" ? "Paste your credentials — no redirect needed" : "Select a tool to connect via OAuth"}
                        </p>
                    </div>
                    <button
                        onClick={onClose}
                        className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-accent text-muted-foreground hover:text-foreground transition-colors"
                    >
                        <X className="w-4 h-4" />
                    </button>
                </div>

                {/* Tabs */}
                <div className="flex border-b border-border">
                    <button
                        onClick={() => setActiveTab("apikey")}
                        className={cn(
                            "flex-1 py-2.5 text-xs font-medium transition-colors border-b-2",
                            activeTab === "apikey"
                                ? "border-primary text-foreground"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        API Key
                    </button>
                    <button
                        onClick={() => setActiveTab("oauth")}
                        className={cn(
                            "flex-1 py-2.5 text-xs font-medium transition-colors border-b-2",
                            activeTab === "oauth"
                                ? "border-primary text-foreground"
                                : "border-transparent text-muted-foreground hover:text-foreground"
                        )}
                    >
                        OAuth
                    </button>
                </div>

                {/* Error banner */}
                {error && (
                    <div className="mx-4 mt-3 flex items-start gap-2 text-sm text-destructive bg-destructive/10 border border-destructive/20 px-3 py-2 rounded-xl">
                        <AlertCircle className="w-4 h-4 flex-shrink-0 mt-0.5" />
                        <span className="flex-1">{error}</span>
                        <button onClick={() => setError(null)} className="flex-shrink-0 hover:opacity-70">
                            <X className="w-3.5 h-3.5" />
                        </button>
                    </div>
                )}

                {/* API Key Panel */}
                {activeTab === "apikey" && (
                    <div className="p-4 flex flex-col gap-4 max-h-[60vh] overflow-y-auto custom-scrollbar">
                        {/* Tool chip selector */}
                        <div>
                            <p className="text-xs text-muted-foreground mb-2 font-medium uppercase tracking-wide">Platform</p>
                            <div className="flex flex-wrap gap-2">
                                {TOOL_REGISTRY.map((tool) => {
                                    const isOAuthOnly = OAUTH_ONLY_TOOLS.has(tool.id);
                                    const iconUrl = getBrandIconUrl(tool.id);
                                    return (
                                        <button
                                            key={tool.id}
                                            onClick={() => handleSelectTool(tool.id)}
                                            disabled={isOAuthOnly}
                                            title={isOAuthOnly ? `${tool.name} requires OAuth` : undefined}
                                            className={cn(
                                                "flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium transition-colors",
                                                isOAuthOnly
                                                    ? "opacity-40 cursor-not-allowed border-border text-muted-foreground"
                                                    : selectedTool === tool.id
                                                    ? "border-primary bg-primary/10 text-primary"
                                                    : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                                            )}
                                        >
                                            {iconUrl ? (
                                                // eslint-disable-next-line @next/next/no-img-element
                                                <img src={iconUrl} alt="" width={13} height={13} className="object-contain rounded-sm" />
                                            ) : (
                                                <span className="w-3 h-3 rounded-sm bg-muted flex items-center justify-center text-[9px] font-bold">
                                                    {tool.name[0]}
                                                </span>
                                            )}
                                            {tool.name}
                                            {isOAuthOnly && <span className="text-[9px] opacity-60">OAuth only</span>}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>

                        {/* Dynamic credential form */}
                        {config && (
                            <div className="flex flex-col gap-3">
                                {/* Scopes note */}
                                <div className="flex items-start gap-2 bg-primary/5 border border-primary/15 rounded-lg px-3 py-2">
                                    <AlertCircle className="w-3.5 h-3.5 text-primary flex-shrink-0 mt-0.5" />
                                    <span className="text-xs text-primary/80">Required access: {config.scopes}</span>
                                </div>

                                {/* Fields */}
                                {config.fields.map((field) => (
                                    <div key={field.key}>
                                        <label className="text-xs text-muted-foreground font-medium uppercase tracking-wide block mb-1.5">
                                            {field.label}
                                        </label>
                                        <input
                                            type={field.type}
                                            placeholder={field.placeholder}
                                            value={credentials[field.key] ?? ""}
                                            onChange={(e) =>
                                                setCredentials((prev) => ({ ...prev, [field.key]: e.target.value }))
                                            }
                                            className="w-full bg-background border border-border rounded-lg px-3 py-2 text-xs font-mono text-foreground placeholder:text-muted-foreground/50 focus:outline-none focus:border-primary transition-colors"
                                        />
                                    </div>
                                ))}

                                {/* Hint */}
                                <p className="text-xs text-muted-foreground leading-relaxed">{config.hint}</p>

                                {/* Success state */}
                                {successTool === selectedTool ? (
                                    <div className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-emerald-500/10 text-emerald-500 text-sm font-medium border border-emerald-500/20">
                                        <CheckCircle2 className="w-4 h-4" /> Connected
                                    </div>
                                ) : (
                                    <button
                                        onClick={handleApiKeyConnect}
                                        disabled={!allFieldsFilled || connecting}
                                        className="flex items-center justify-center gap-2 py-2.5 rounded-xl bg-primary text-primary-foreground text-xs font-semibold hover:bg-primary/90 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                                    >
                                        {connecting ? (
                                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                        ) : (
                                            <Check className="w-3.5 h-3.5" />
                                        )}
                                        {connecting ? "Connecting…" : `Connect ${TOOL_REGISTRY.find(t => t.id === selectedTool)?.name}`}
                                    </button>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* OAuth Panel */}
                {activeTab === "oauth" && (
                    <div className="flex flex-col gap-1 p-3 max-h-[60vh] overflow-y-auto custom-scrollbar">
                        {TOOL_REGISTRY.map((tool) => {
                            const connected = isConnected(tool.id);
                            const iconUrl = getBrandIconUrl(tool.id);
                            const isOAuthBusy = oauthBusy === tool.id;
                            const isDisconnectingThis = disconnecting === tool.id;
                            const busy = isOAuthBusy || isDisconnectingThis;

                            return (
                                <div
                                    key={tool.id}
                                    className="flex items-center gap-3 px-3 py-2.5 rounded-xl hover:bg-accent/50 transition-colors"
                                >
                                    <div className="w-8 h-8 rounded-lg bg-accent flex items-center justify-center flex-shrink-0 overflow-hidden">
                                        {iconUrl ? (
                                            // eslint-disable-next-line @next/next/no-img-element
                                            <img src={iconUrl} alt={tool.name} width={20} height={20} className="object-contain" />
                                        ) : (
                                            <span className="text-xs font-bold text-muted-foreground">{tool.name[0]}</span>
                                        )}
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <p className="text-sm font-medium text-foreground">{tool.name}</p>
                                        {connected ? (
                                            <p className="text-xs text-emerald-500 flex items-center gap-1">
                                                <CheckCircle2 className="w-3 h-3" /> Connected
                                            </p>
                                        ) : (
                                            <p className="text-xs text-muted-foreground">Not connected</p>
                                        )}
                                    </div>
                                    {connected ? (
                                        <button
                                            onClick={() => handleDisconnect(tool.id)}
                                            disabled={busy}
                                            className="text-xs px-3 py-1.5 rounded-lg bg-destructive/10 text-destructive hover:bg-destructive hover:text-white transition-colors disabled:opacity-50 flex items-center gap-1"
                                        >
                                            {isDisconnectingThis ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                                            Disconnect
                                        </button>
                                    ) : (
                                        <button
                                            onClick={() => handleOAuthConnect(tool.id)}
                                            disabled={busy}
                                            className="text-xs px-3 py-1.5 rounded-lg bg-primary text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50 flex items-center gap-1"
                                        >
                                            {isOAuthBusy ? <Loader2 className="w-3 h-3 animate-spin" /> : <ExternalLink className="w-3 h-3" />}
                                            Connect
                                        </button>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}

                {/* Footer */}
                <div className="px-5 py-3 border-t border-border">
                    <p className="text-xs text-muted-foreground text-center">
                        {activeTab === "apikey"
                            ? "Credentials are encrypted and stored securely."
                            : "You'll be redirected to the tool's OAuth page to authorise access."}
                    </p>
                </div>
            </div>
        </div>
    );
}
```

- [ ] **Step 5: Run the new tests — expect 3 PASS**

```bash
cd frontend && npx vitest run tests/collapsible-sidebar.test.tsx
```

Expected: all tests PASS including the 3 new ones.

- [ ] **Step 6: Run the full frontend test suite**

```bash
cd frontend && npx vitest run
```

Expected: all previously passing tests still PASS. Fix any type errors from the updated `useToolConnections` mock if needed (add `connectViaApiKey: vi.fn()` to any other test files that mock `useToolConnections`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/dashboard/collapsible-sidebar.tsx frontend/tests/collapsible-sidebar.test.tsx
git commit -m "feat: replace ConnectToolModal with tabbed API Key / OAuth design"
```

---

### Task 4: Fix mocks in other test files that mock `useToolConnections`

**Files:**
- Check and update any test file that mocks `useToolConnections` without `connectViaApiKey`

- [ ] **Step 1: Find all test files mocking `useToolConnections`**

```bash
cd frontend && grep -r "useToolConnections" tests/ -l
```

- [ ] **Step 2: Add `connectViaApiKey: vi.fn()` to each mock that is missing it**

For each file found, locate the `useToolConnections` mock and ensure it includes:

```typescript
connectViaApiKey: vi.fn(),
```

- [ ] **Step 3: Run the full test suite one final time**

```bash
cd frontend && npx vitest run
```

Expected: all tests PASS with no TypeScript errors.

- [ ] **Step 4: Final commit**

```bash
git add frontend/tests/
git commit -m "test: add connectViaApiKey to useToolConnections mocks across test suite"
```
