# Help Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a ? icon to the chat header that opens a lightweight popover listing what users can do with each connected tool, and tell the AI it can occasionally mention this icon when a user asks something out of scope.

**Architecture:** A static capability map in `src/lib/tool-capabilities.ts` drives a popover component built inline in `chat-interface.tsx` using React state and a click-outside ref — no new dependencies. The popover filters to connected tools only via `useToolConnections`. A single line added to `RESPONSE_FORMAT` handles the AI nudge.

**Tech Stack:** Next.js 15, React 19, TypeScript, Tailwind CSS, lucide-react, Vitest + source-level tests.

**Prerequisite:** `2026-05-29-response-format.md` plan must be complete — this plan adds one line to the `RESPONSE_FORMAT` constant created there.

---

### Task 1: Create tool capabilities data

**Files:**
- Create: `frontend/src/lib/tool-capabilities.ts`
- Create: `frontend/tests/tool-capabilities.test.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/tests/tool-capabilities.test.ts`:

```typescript
import { readFileSync } from "fs";
import { resolve } from "path";

const source = readFileSync(
    resolve(__dirname, "../src/lib/tool-capabilities.ts"),
    "utf8"
);

describe("tool-capabilities", () => {
    it("exports TOOL_CAPABILITIES", () => {
        expect(source).toContain("export const TOOL_CAPABILITIES");
    });

    it("exports ToolCapabilityEntry type", () => {
        expect(source).toContain("ToolCapabilityEntry");
    });

    it("covers all 7 supported tool types", () => {
        const tools = ["gmail", "calendar", "slack", "jira", "github", "dropbox", "trello"];
        for (const tool of tools) {
            expect(source).toContain(`"${tool}"`);
        }
    });

    it("each tool has a label and capabilities array", () => {
        expect(source).toContain("label:");
        expect(source).toContain("capabilities:");
    });

    it("no tool has fewer than 3 capability strings", () => {
        // Rough check: at least 3 capability strings per tool (21+ total)
        const matches = source.match(/"[A-Z][^"]{10,}"/g) ?? [];
        expect(matches.length).toBeGreaterThanOrEqual(21);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npx vitest run tests/tool-capabilities.test.ts
```

Expected: FAIL — `ENOENT: no such file or directory` for the source file

- [ ] **Step 3: Create `frontend/src/lib/tool-capabilities.ts`**

```typescript
import type { ToolType } from "@/hooks/use-tool-connections";

export interface ToolCapabilityEntry {
    label: string;
    capabilities: string[];
}

export const TOOL_CAPABILITIES: Record<ToolType, ToolCapabilityEntry> = {
    gmail: {
        label: "Gmail",
        capabilities: [
            "Read and search your emails",
            "Send, reply to, or forward emails",
            "Draft emails for your review",
            "Summarise inbox threads",
        ],
    },
    calendar: {
        label: "Calendar",
        capabilities: [
            "List upcoming events",
            "Create, update, or delete events",
            "Schedule meetings with natural language",
            "Search events by date or title",
        ],
    },
    slack: {
        label: "Slack",
        capabilities: [
            "Read channels and messages",
            "Send messages or DMs (with your confirmation)",
            "Search conversations",
            "List workspace users",
        ],
    },
    jira: {
        label: "Jira",
        capabilities: [
            "Search and list issues with JQL",
            "Create issues (with your confirmation)",
            "Transition issue status",
            "View sprint progress",
        ],
    },
    github: {
        label: "GitHub",
        capabilities: [
            "List repositories and pull requests",
            "View open issues and notifications",
            "Check PR status and review requests",
        ],
    },
    dropbox: {
        label: "Dropbox",
        capabilities: [
            "List files and folders",
            "Upload or download files",
            "Move, rename, or delete files (with your confirmation)",
            "Create shared links",
        ],
    },
    trello: {
        label: "Trello",
        capabilities: [
            "View boards, lists, and cards",
            "Create and move cards",
            "Check due dates and assignments",
        ],
    },
};
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npx vitest run tests/tool-capabilities.test.ts
```

Expected: 5 PASSED

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/tool-capabilities.ts frontend/tests/tool-capabilities.test.ts
git commit -m "feat: add static tool capability map for help center"
```

---

### Task 2: Add ? icon and help popover to chat header

**Files:**
- Modify: `frontend/src/components/dashboard/chat-interface.tsx`
- Modify: `frontend/tests/chat-interface.test.tsx`

- [ ] **Step 1: Add new tests to `frontend/tests/chat-interface.test.tsx`**

Append these cases inside the existing `describe` block in `frontend/tests/chat-interface.test.tsx`:

```typescript
    it("imports HelpCircle from lucide-react", () => {
        expect(source).toMatch(/import[^;]*HelpCircle[^;]*from "lucide-react"/);
    });

    it("imports useToolConnections hook", () => {
        expect(source).toContain('from "@/hooks/use-tool-connections"');
    });

    it("imports TOOL_CAPABILITIES", () => {
        expect(source).toContain('from "@/lib/tool-capabilities"');
    });

    it("has showHelp state", () => {
        expect(source).toContain("showHelp");
        expect(source).toContain("setShowHelp");
    });

    it("renders the help button with aria-label", () => {
        expect(source).toContain('aria-label="What can ByteOps do?"');
    });

    it("renders HelpCircle icon", () => {
        expect(source).toContain("<HelpCircle");
    });

    it("renders 'What can I help you with?' popover heading", () => {
        expect(source).toContain("What can I help you with?");
    });

    it("has click-outside handler to close popover", () => {
        expect(source).toContain("handleClickOutside");
        expect(source).toContain("removeEventListener");
    });
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd frontend && npx vitest run tests/chat-interface.test.tsx
```

Expected: The 8 new tests FAIL, existing tests still PASS

- [ ] **Step 3: Add imports to `chat-interface.tsx`**

In `frontend/src/components/dashboard/chat-interface.tsx`, find the existing import line:

```typescript
import { Send, User, Paperclip, Mic, Mail, ExternalLink, Loader2 } from "lucide-react";
```

Replace with:

```typescript
import { Send, User, Paperclip, Mic, Mail, ExternalLink, Loader2, HelpCircle } from "lucide-react";
```

Then after the existing `import { ByteOpsLogoMark } from "@/lib/brand-icons";` line, add:

```typescript
import { useToolConnections } from "@/hooks/use-tool-connections";
import { TOOL_CAPABILITIES } from "@/lib/tool-capabilities";
```

- [ ] **Step 4: Add `showHelp` state and `helpRef` inside the component**

In `ChatInterface`, after the existing state declarations (around line 107), add:

```typescript
    const [showHelp, setShowHelp] = useState(false);
    const helpRef = useRef<HTMLDivElement>(null);
    const { connections } = useToolConnections();
    const connectedTools = connections.filter(c => c.status === "connected");
```

- [ ] **Step 5: Add click-outside effect**

After the existing `useEffect` blocks inside `ChatInterface`, add:

```typescript
    useEffect(() => {
        function handleClickOutside(e: MouseEvent) {
            if (helpRef.current && !helpRef.current.contains(e.target as Node)) {
                setShowHelp(false);
            }
        }
        if (showHelp) {
            document.addEventListener("mousedown", handleClickOutside);
            return () => document.removeEventListener("mousedown", handleClickOutside);
        }
    }, [showHelp]);
```

- [ ] **Step 6: Replace the chat header JSX**

Find the current chat header block in the return statement:

```tsx
            {/* Chat Header */}
            <div className="p-4 border-b border-border flex-shrink-0">
                <h2 className="font-semibold text-foreground">ByteOps AI</h2>
                <p className="text-sm text-muted-foreground">AI-enabled workspace</p>
            </div>
```

Replace with:

```tsx
            {/* Chat Header */}
            <div className="p-4 border-b border-border flex-shrink-0 flex items-center justify-between">
                <div>
                    <h2 className="font-semibold text-foreground">ByteOps AI</h2>
                    <p className="text-sm text-muted-foreground">AI-enabled workspace</p>
                </div>

                {/* Help popover */}
                <div className="relative" ref={helpRef}>
                    <button
                        onClick={() => setShowHelp(v => !v)}
                        aria-label="What can ByteOps do?"
                        className="text-muted-foreground hover:text-foreground transition-colors p-1.5 rounded-md hover:bg-accent"
                    >
                        <HelpCircle className="w-4 h-4" />
                    </button>

                    {showHelp && (
                        <div className="absolute right-0 top-9 z-50 w-72 rounded-xl border border-border bg-background shadow-lg p-4 text-sm">
                            <p className="font-medium text-foreground mb-3">What can I help you with?</p>
                            {connectedTools.length === 0 ? (
                                <p className="text-muted-foreground">
                                    Connect a tool in Settings → Connections to get started.
                                </p>
                            ) : (
                                <div className="space-y-3 max-h-64 overflow-y-auto custom-scrollbar">
                                    {connectedTools.map(tool => {
                                        const entry = TOOL_CAPABILITIES[tool.tool_type];
                                        if (!entry) return null;
                                        return (
                                            <div key={tool.tool_type}>
                                                <p className="font-medium text-foreground">{entry.label}</p>
                                                <ul className="mt-1 space-y-0.5">
                                                    {entry.capabilities.map(cap => (
                                                        <li key={cap} className="text-muted-foreground">
                                                            · {cap}
                                                        </li>
                                                    ))}
                                                </ul>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
```

- [ ] **Step 7: Run all chat-interface tests**

```bash
cd frontend && npx vitest run tests/chat-interface.test.tsx
```

Expected: All tests PASSED (both existing and new 8)

- [ ] **Step 8: Run the full frontend test suite to check for regressions**

```bash
cd frontend && npx vitest run
```

Expected: All tests PASSED

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/dashboard/chat-interface.tsx frontend/tests/chat-interface.test.tsx
git commit -m "feat: add help popover with per-tool capability list to chat header"
```

---

### Task 3: Tell the AI about the ? icon

**Files:**
- Modify: `backend/app/agents/response_format.py`
- Modify: `backend/tests/test_response_format.py`

- [ ] **Step 1: Add test for help icon mention**

In `backend/tests/test_response_format.py`, add one new test:

```python
def test_response_format_mentions_help_icon():
    assert "? Help button" in RESPONSE_FORMAT
```

- [ ] **Step 2: Run the new test to verify it fails**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_response_format_mentions_help_icon -v
```

Expected: FAILED — `AssertionError`

- [ ] **Step 3: Add the help icon line to `RESPONSE_FORMAT`**

In `backend/app/agents/response_format.py`, append one line to the `RESPONSE_FORMAT` string before the closing `"""`:

```python
RESPONSE_FORMAT = """\

Response style — follow strictly:
- Write in plain, natural prose. Like a helpful colleague in a chat, not a document.
- No headers (###, ##, #). Ever.
- No bold (**text**) or italic (*text*) for decoration or emphasis.
- No horizontal rules (---).
- Use a numbered list only when steps must be done in a specific order (3+ steps).
- Use a plain bullet list only when there are 4+ genuinely parallel items that read \
awkwardly as prose.
- For structured data only (issue lists, file listings, calendar events), a minimal \
plain table is allowed.
- One clear sentence beats three padded ones. Keep it short.
- If the user asks something clearly outside what you can do, you may occasionally \
mention the ? Help button at the top of the chat to see what's available. Only say \
this when the user seems genuinely confused — not on every out-of-scope reply.
"""
```

- [ ] **Step 4: Run all backend response-format tests**

```bash
cd backend && python -m pytest tests/test_response_format.py -v
```

Expected: All 14 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/response_format.py backend/tests/test_response_format.py
git commit -m "feat: tell AI about the ? Help button for out-of-scope nudge"
```
