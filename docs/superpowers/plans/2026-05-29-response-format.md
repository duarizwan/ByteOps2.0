# Response Format Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace per-agent "Format in clean Markdown" instructions with a single shared `RESPONSE_FORMAT` constant so all 7 AI agents produce plain conversational prose instead of markdown-heavy output.

**Architecture:** A new module `backend/app/agents/response_format.py` exports one string constant. Each agent file imports it and concatenates it onto its system prompt string, removing the existing markdown formatting line. The orchestrator injects it via its f-string.

**Tech Stack:** Python 3.10+, pytest, existing agent files in `backend/app/agents/`.

---

### Task 1: Create `response_format.py` and write tests (TDD)

**Files:**
- Create: `backend/app/agents/response_format.py`
- Create: `backend/tests/test_response_format.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_response_format.py`:

```python
"""Tests for the shared RESPONSE_FORMAT constant."""
from app.agents.response_format import RESPONSE_FORMAT
from app.agents.orchestrator import build_system_prompt
from app.agents.gmail_agent import GMAIL_SYSTEM_PROMPT
from app.agents.calendar_agent import CALENDAR_SYSTEM_PROMPT
from app.agents.github_agent import GITHUB_SYSTEM_PROMPT
from app.agents.slack_agent import SLACK_SYSTEM_PROMPT
from app.agents.jira_agent import JIRA_SYSTEM_PROMPT
from app.agents.dropbox_agent import DROPBOX_SYSTEM_PROMPT


def test_response_format_bans_headers():
    assert "No headers" in RESPONSE_FORMAT


def test_response_format_bans_bold():
    assert "No bold" in RESPONSE_FORMAT


def test_response_format_bans_dividers():
    assert "No horizontal rules" in RESPONSE_FORMAT


def test_response_format_allows_tables_for_structured_data():
    assert "plain table is allowed" in RESPONSE_FORMAT


def test_response_format_is_string():
    assert isinstance(RESPONSE_FORMAT, str)
    assert len(RESPONSE_FORMAT) > 50


def test_orchestrator_prompt_contains_format_rules():
    prompt = build_system_prompt([])
    assert "No headers" in prompt
    assert "plain, natural prose" in prompt


def test_orchestrator_prompt_no_legacy_markdown_instruction():
    prompt = build_system_prompt([])
    assert "Use Markdown for structured answers" not in prompt


def test_gmail_prompt_contains_format_rules():
    assert "No headers" in GMAIL_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in GMAIL_SYSTEM_PROMPT


def test_calendar_prompt_contains_format_rules():
    assert "No headers" in CALENDAR_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in CALENDAR_SYSTEM_PROMPT


def test_github_prompt_contains_format_rules():
    assert "No headers" in GITHUB_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in GITHUB_SYSTEM_PROMPT


def test_slack_prompt_contains_format_rules():
    assert "No headers" in SLACK_SYSTEM_PROMPT
    assert "Format all responses in clean Markdown" not in SLACK_SYSTEM_PROMPT


def test_jira_prompt_contains_format_rules():
    assert "No headers" in JIRA_SYSTEM_PROMPT
    assert "plain table is allowed" in JIRA_SYSTEM_PROMPT
    assert "Format responses in clean Markdown tables" not in JIRA_SYSTEM_PROMPT


def test_dropbox_prompt_contains_format_rules():
    assert "No headers" in DROPBOX_SYSTEM_PROMPT
    assert "plain table is allowed" in DROPBOX_SYSTEM_PROMPT
    assert "Format file listings as clean Markdown tables" not in DROPBOX_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests — expect ImportError (module doesn't exist yet)**

```bash
cd backend && python -m pytest tests/test_response_format.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'app.agents.response_format'`

- [ ] **Step 3: Create `backend/app/agents/response_format.py`**

```python
"""Shared response-format instruction injected into every agent system prompt."""

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
"""
```

- [ ] **Step 4: Run the constant tests — they should pass, agent tests still fail**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_response_format_bans_headers tests/test_response_format.py::test_response_format_bans_bold tests/test_response_format.py::test_response_format_bans_dividers tests/test_response_format.py::test_response_format_allows_tables_for_structured_data tests/test_response_format.py::test_response_format_is_string -v
```

Expected: 5 PASSED

- [ ] **Step 5: Commit the constant and tests**

```bash
git add backend/app/agents/response_format.py backend/tests/test_response_format.py
git commit -m "feat: add shared RESPONSE_FORMAT constant for agent prose style"
```

---

### Task 2: Update orchestrator system prompt

**Files:**
- Modify: `backend/app/agents/orchestrator.py`

- [ ] **Step 1: Add import at the top of orchestrator.py**

In `backend/app/agents/orchestrator.py`, after the existing imports (around line 16), add:

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Replace the `# Response formatting` block in `build_system_prompt`**

Find this block near the end of the returned f-string (lines 284–288):

```python
# Response formatting
- Use Markdown for structured answers.
- For short replies, plain prose is fine.
- When listing capabilities, be accurate — never invent tools that aren't listed above.
"""
```

Replace with:

```python
{RESPONSE_FORMAT}
- When listing capabilities, be accurate — never invent tools that aren't listed above.
"""
```

- [ ] **Step 3: Run orchestrator tests**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_orchestrator_prompt_contains_format_rules tests/test_response_format.py::test_orchestrator_prompt_no_legacy_markdown_instruction -v
```

Expected: 2 PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/orchestrator.py
git commit -m "feat: inject RESPONSE_FORMAT into orchestrator system prompt"
```

---

### Task 3: Update Gmail agent

**Files:**
- Modify: `backend/app/agents/gmail_agent.py`

- [ ] **Step 1: Add import after existing imports in gmail_agent.py**

After the existing imports block (around line 25), add:

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Remove the markdown line and append RESPONSE_FORMAT**

Find in `GMAIL_SYSTEM_PROMPT`:
```
- Format all responses in clean Markdown.
```
Delete that line entirely. Then change the closing `"""` of `GMAIL_SYSTEM_PROMPT` to `""" + RESPONSE_FORMAT`.

The end of the constant should look like:

```python
GMAIL_SYSTEM_PROMPT = """\
You are the ByteOps Gmail Specialist. You have tools to read, search, send, \
reply to, forward, and draft emails on behalf of the user.

Guidelines:
- Always act on the user's intent directly; do not narrate what you are about to do.
- When summarising emails, be concise: sender, subject, and a 1-2 sentence summary.
- For destructive or send actions (send_email, reply_to_email, forward_email),
  always confirm the full details with the user before calling the tool unless
  they have already explicitly confirmed.
- If a tool returns an error, explain it clearly and suggest what to do next.

IMPORTANT — Scope:
- You only handle Gmail. You have NO access to Google Calendar, GitHub, Slack, or any other service.
- If the user asks about calendar events, scheduling, or any non-Gmail service, do NOT attempt
  to help or apologise. Instead say exactly: "That sounds like a calendar/GitHub request — please
  send a new message mentioning 'calendar' or 'GitHub' and the routing system will send it to
  the right specialist."
""" + RESPONSE_FORMAT
```

- [ ] **Step 3: Run Gmail test**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_gmail_prompt_contains_format_rules -v
```

Expected: PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/gmail_agent.py
git commit -m "feat: inject RESPONSE_FORMAT into Gmail agent system prompt"
```

---

### Task 4: Update Calendar agent

**Files:**
- Modify: `backend/app/agents/calendar_agent.py`

- [ ] **Step 1: Add import after existing imports**

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Remove markdown line and append RESPONSE_FORMAT**

Find and delete from `CALENDAR_SYSTEM_PROMPT`:
```
Format all responses in clean Markdown.
```

Change the closing `"""` to `""" + RESPONSE_FORMAT`. The constant should end as:

```python
CALENDAR_SYSTEM_PROMPT = """\
You are the ByteOps Calendar Specialist. You have tools to read, search, create, update,
and delete calendar events on behalf of the user.

Guidelines:
- Always act on the user's intent directly; do not narrate what you are about to do.
- When listing events, be concise: title, date/time, location (if present), and attendees.
- For time range queries, default to listing events for the next 7 days if no range is specified.

Datetime format rules (CRITICAL — follow exactly):
- Use ISO 8601 format WITHOUT timezone offset: '2025-06-01T10:00:00' (no +05:00, no Z suffix)
- Always pass the 'timezone' parameter separately using IANA names: 'Asia/Karachi', 'America/New_York',
  'Europe/London', 'UTC', etc. Default to 'UTC' if the user doesn't specify.
- For all-day events, use date-only format: '2025-06-01' (no time component)
- For list/search time bounds, use UTC with Z suffix: '2025-06-01T00:00:00Z'
- Use quick_add for natural-language scheduling like "lunch tomorrow at 1pm" — it's the fastest tool.

Confirmation rules:
- For create_event: confirm title, date/time, and timezone with user before calling.
- For delete_event and update_event: always confirm full details before calling.

If a tool returns a permission error (403), tell the user:
  "Your Calendar connection needs to be reconnected with full access. Please go to
   Settings → Connections, disconnect Calendar, and reconnect it."
""" + RESPONSE_FORMAT
```

- [ ] **Step 3: Run Calendar test**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_calendar_prompt_contains_format_rules -v
```

Expected: PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/calendar_agent.py
git commit -m "feat: inject RESPONSE_FORMAT into Calendar agent system prompt"
```

---

### Task 5: Update GitHub agent

**Files:**
- Modify: `backend/app/agents/github_agent.py`

- [ ] **Step 1: Add import**

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Remove markdown line and append RESPONSE_FORMAT**

Delete from `GITHUB_SYSTEM_PROMPT`:
```
- Format all responses in clean Markdown.
```

Change closing `"""` to `""" + RESPONSE_FORMAT`. End result:

```python
GITHUB_SYSTEM_PROMPT = """\
You are the ByteOps GitHub Specialist. You have tools to read repositories,
pull requests, issues, and notifications from the user's GitHub account.

Guidelines:
- Always act on the user's intent directly; do not narrate what you are about to do.
- When listing repositories or PRs, be concise: name, status, and relevant metadata.
- For 'open PRs', first call list_repos to know what repos to check, then list_prs
  for the most recently active ones.
- If a tool returns an error (e.g., 404 for unknown repo), explain it clearly.
- Never invent repository names or PR numbers.
""" + RESPONSE_FORMAT
```

- [ ] **Step 3: Run GitHub test**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_github_prompt_contains_format_rules -v
```

Expected: PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/github_agent.py
git commit -m "feat: inject RESPONSE_FORMAT into GitHub agent system prompt"
```

---

### Task 6: Update Slack agent

**Files:**
- Modify: `backend/app/agents/slack_agent.py`

- [ ] **Step 1: Add import**

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Remove markdown line and append RESPONSE_FORMAT**

Delete from `SLACK_SYSTEM_PROMPT`:
```
- Format all responses in clean Markdown.
```

Change closing `"""` to `""" + RESPONSE_FORMAT`. End result:

```python
SLACK_SYSTEM_PROMPT = """\
You are the ByteOps Slack Specialist. You have tools to read channels, messages, threads, \
send messages, DMs, manage reactions, and list users.

Guidelines:
- Act on the user's intent directly; do not narrate what you are about to do.
- When listing channels or messages, be concise: name/user and key content.
- For send_message and send_dm, always confirm the content and recipient with the user before \
calling the tool unless they have already explicitly confirmed.
- For delete_message and update_message, always confirm with the user first.
- If a tool returns an error (e.g., missing scope), explain it and suggest reconnecting Slack \
in Settings → Connections with the required scopes.
""" + RESPONSE_FORMAT
```

- [ ] **Step 3: Run Slack test**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_slack_prompt_contains_format_rules -v
```

Expected: PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/slack_agent.py
git commit -m "feat: inject RESPONSE_FORMAT into Slack agent system prompt"
```

---

### Task 7: Update Jira agent

**Files:**
- Modify: `backend/app/agents/jira_agent.py`

- [ ] **Step 1: Add import**

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Remove markdown line and append RESPONSE_FORMAT**

Delete from `JIRA_SYSTEM_PROMPT`:
```
- Format responses in clean Markdown tables for issue lists.
```

Change closing `"""` to `""" + RESPONSE_FORMAT`. End result:

```python
JIRA_SYSTEM_PROMPT = """\
You are the ByteOps Jira Specialist. You have tools to manage Jira issues, projects, sprints, and comments.

Guidelines:
- Act on the user's intent directly.
- For create_issue: always confirm project, summary, and type with user unless already specified.
- For transition_issue: first call get_transitions to see valid states, then transition.
- For destructive actions (delete_comment), confirm with user first.
- Use JQL for flexible issue searches: 'project = KEY', 'assignee = currentUser()', \
'status = "In Progress"', 'sprint in openSprints()'.
- If you get a 401/403 error, tell the user to reconnect Jira in Settings → Connections.
""" + RESPONSE_FORMAT
```

Note: RESPONSE_FORMAT already says "For structured data only (issue lists, file listings, calendar events), a minimal plain table is allowed" — tables are preserved for Jira issue lists.

- [ ] **Step 3: Run Jira test**

```bash
cd backend && python -m pytest tests/test_response_format.py::test_jira_prompt_contains_format_rules -v
```

Expected: PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/jira_agent.py
git commit -m "feat: inject RESPONSE_FORMAT into Jira agent system prompt"
```

---

### Task 8: Update Dropbox agent

**Files:**
- Modify: `backend/app/agents/dropbox_agent.py`

- [ ] **Step 1: Add import**

```python
from app.agents.response_format import RESPONSE_FORMAT
```

- [ ] **Step 2: Remove markdown line and append RESPONSE_FORMAT**

Delete from `DROPBOX_SYSTEM_PROMPT`:
```
- Format file listings as clean Markdown tables with name, type, size, modified date.
```

Replace it with a plain columns instruction and append RESPONSE_FORMAT:
```
- For file listings, use a table with columns: name, type, size, modified date.
```

Change closing `"""` to `""" + RESPONSE_FORMAT`. End result:

```python
DROPBOX_SYSTEM_PROMPT = """\
You are the ByteOps Dropbox Specialist. You have tools to manage files and folders in the user's Dropbox.

Guidelines:
- Act on the user's intent directly.
- Paths must start with / (e.g. /Documents/report.pdf). Root folder is empty string '' or '/'.
- For upload_file: content must be base64-encoded. Tell the user if they need to provide file content.
- For delete_path and move_path: always confirm with the user before calling the tool.
- For download_file: files larger than 1MB return a warning — mention this to users.
- create_shared_link creates a public link; warn the user about privacy implications.
- For file listings, use a table with columns: name, type, size, modified date.
- If you get an auth error, tell the user to reconnect Dropbox in Settings → Connections.
""" + RESPONSE_FORMAT
```

- [ ] **Step 3: Run all tests**

```bash
cd backend && python -m pytest tests/test_response_format.py -v
```

Expected: All 13 tests PASSED

- [ ] **Step 4: Commit**

```bash
git add backend/app/agents/dropbox_agent.py
git commit -m "feat: inject RESPONSE_FORMAT into Dropbox agent system prompt"
```
