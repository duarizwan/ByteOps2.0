"""Orchestrator Agent — The central brain of ByteOps.

Powered by Claude (Anthropic). Reasons, responds, and routes to specialist
tool-agents (Gmail, Calendar, GitHub, etc.) as sub-routines.

- Receives the full conversation history from the database
- Streams the reply back token by token via an asyncio.Queue
- Has a detailed system prompt that explains its role and capabilities
"""

import asyncio
import logging
import string
import anthropic
from app.core.config import get_settings
from app.agents.response_format import RESPONSE_FORMAT

logger = logging.getLogger(__name__)

CLAUDE_MODEL = "claude-sonnet-4-6"

# Pre-built translator reused on every detect_intent call
_PUNCT_TRANSLATOR = str.maketrans('', '', string.punctuation)

# Module-level Claude client — created once, reused for all requests
_claude_client: anthropic.AsyncAnthropic | None = None


def _get_claude_client() -> anthropic.AsyncAnthropic:
    """Return (or lazily create) the shared Claude AsyncAnthropic client."""
    global _claude_client
    if _claude_client is None:
        settings = get_settings()
        _claude_client = anthropic.AsyncAnthropic(
            api_key=settings.claude_api_key,
        )
    return _claude_client

# ── Intent detection ─────────────────────────────────────────────────────────
# Keyword sets for each specialist domain.
# This avoids an extra LLM call just for routing — fast and free.

_GMAIL_KEYWORDS = {
    "email", "gmail", "inbox", "unread", "mail", "emails",
    "sender", "sent", "draft", "drafts", "reply", "forward",
    "compose", "subject", "attachment", "thread", "newsletter",
    "subscribe", "unsubscribe", "mailing",
}

_CALENDAR_KEYWORDS = {
    "agenda", "calendar", "schedule", "meeting", "meetings", "event", "events",
    "appointment", "remind", "reminder", "availability", "busy", "free slot",
}

_GITHUB_KEYWORDS = {
    "github", "repo", "repos", "repository", "repositories", "pull", "pr", "prs",
    "issue", "issues", "commit", "commits", "branch", "branches", "merge",
    "open prs", "pull request", "pull requests", "code review", "review",
}

_SLACK_KEYWORDS = {
    "slack", "channel", "channels", "message", "messages", "dm", "direct message",
    "workspace", "thread", "threads", "mention", "mentions", "reaction",
}

_JIRA_KEYWORDS = {
    "jira", "ticket", "tickets", "sprint", "sprints", "backlog", "epic", "epics",
    "story", "stories", "task", "tasks", "board", "boards", "project key",
    "in progress", "to do", "done", "assignee", "jql",
}

_DROPBOX_KEYWORDS = {
    "dropbox", "file", "files", "folder", "folders", "upload", "download",
    "shared link", "share link", "storage", "document", "documents",
}


def detect_intent(message: str, history: list[dict] | None = None) -> str:
    """Fast keyword-based intent detection — no LLM call needed.

    Returns one of: 'gmail', 'calendar', 'github', 'general'.
    """
    lower = message.lower()
    clean_lower = lower.translate(_PUNCT_TRANSLATOR)
    words = set(clean_lower.split())

    # ── Step 1: Explicit service name (highest priority) ─────────────────────
    if "calendar" in lower or "google calendar" in lower:
        return "calendar"
    if "github" in lower or "open prs" in lower:
        return "github"
    if "slack" in lower:
        return "slack"
    if "jira" in lower:
        return "jira"
    if "dropbox" in lower:
        return "dropbox"
    if "gmail" in lower or "my inbox" in lower or "my emails" in lower:
        return "gmail"

    # ── Step 2: Score-based keyword matching ──────────────────────────────────
    scores = {
        "gmail":    len(words & _GMAIL_KEYWORDS),
        "calendar": len(words & _CALENDAR_KEYWORDS),
        "github":   len(words & _GITHUB_KEYWORDS),
        "slack":    len(words & _SLACK_KEYWORDS),
        "jira":     len(words & _JIRA_KEYWORDS),
        "dropbox":  len(words & _DROPBOX_KEYWORDS),
    }
    top = max(scores.values())
    if top > 0:
        for service in ("calendar", "github", "slack", "jira", "dropbox", "gmail"):
            if scores[service] == top:
                return service

    # ── Step 3: Context fallback for very short (≤5 word) ambiguous messages ──
    if history and len(words) <= 5:
        last_asst = next((m for m in reversed(history) if m["role"] == "assistant"), None)
        if last_asst and last_asst.get("content"):
            last_lower = last_asst["content"].lower()
            last_clean = last_lower.translate(_PUNCT_TRANSLATOR)
            last_words = set(last_clean.split())

            for svc, kws, name_check in [
                ("gmail",    _GMAIL_KEYWORDS,    "gmail"),
                ("calendar", _CALENDAR_KEYWORDS, "calendar"),
                ("github",   _GITHUB_KEYWORDS,   "github"),
                ("slack",    _SLACK_KEYWORDS,    "slack"),
                ("jira",     _JIRA_KEYWORDS,     "jira"),
                ("dropbox",  _DROPBOX_KEYWORDS,  "dropbox"),
            ]:
                if name_check in last_lower or last_words & kws:
                    return svc

    return "general"


# ── Tool capability registry ──────────────────────────────────────────────────

_TOOL_DESCRIPTIONS: dict[str, dict] = {
    "gmail": {
        "name": "Gmail",
        "capabilities": [
            "list_emails              — list recent inbox emails",
            "search_emails            — search with Gmail queries (is:unread, from:x…)",
            "get_email_content        — read the full body of an email",
            "get_thread               — read an entire email thread",
            "list_labels              — list all Gmail labels",
            "send_email               — compose and send a new email",
            "reply_to_email           — reply to an existing thread",
            "forward_email            — forward an email to someone",
            "create_draft / send_draft — save and send drafts",
            "trash_email              — move email to trash",
            "delete_email_permanently — irreversibly delete an email",
            "mark_as_read/unread      — change read status",
            "apply_label/remove_label — manage labels",
        ],
    },
    "calendar": {
        "name": "Google Calendar",
        "capabilities": [
            "list_events   — list upcoming events",
            "search_events — search by text and time range",
            "get_event     — get full event details",
            "quick_add     — create event from natural language ('lunch tomorrow 1pm')",
            "create_event  — create a new event with full details",
            "update_event  — update an existing event",
            "delete_event  — permanently delete an event",
        ],
    },
    "github": {
        "name": "GitHub",
        "capabilities": [
            "list_repos / list_prs / list_issues — browse repositories",
            "get_pr / get_issue                  — full details",
            "create_repo                         — create a new repository",
            "create_issue / update_issue         — manage issues",
            "close_issue                         — close an issue",
            "create_pr / update_pr / merge_pr / close_pr — manage pull requests",
            "comment_on_issue                    — add a comment",
            "list_notifications                  — GitHub notifications",
        ],
    },
    "slack": {
        "name": "Slack",
        "capabilities": [
            "list_channels / list_my_channels    — browse channels",
            "get_channel_messages                — read channel history",
            "get_thread_replies                  — read a thread",
            "send_message                        — post to a channel",
            "send_dm                             — send a direct message",
            "update_message / delete_message     — edit or delete a message",
            "list_users / get_user_info          — browse workspace members",
            "add_reaction / remove_reaction      — emoji reactions",
        ],
    },
    "jira": {
        "name": "Jira",
        "capabilities": [
            "list_projects                       — list Jira projects",
            "search_issues                       — search with JQL",
            "get_issue                           — full issue details",
            "create_issue / update_issue         — create or edit issues",
            "transition_issue                    — change status (To Do → In Progress → Done)",
            "assign_issue                        — assign to a user",
            "add_comment / update_comment / delete_comment — manage comments",
            "list_boards / list_sprints          — agile board navigation",
            "get_current_user                    — your Jira identity",
        ],
    },
    "dropbox": {
        "name": "Dropbox",
        "capabilities": [
            "list_folder / search_files          — browse and find files",
            "get_metadata                        — file/folder details",
            "download_file / upload_file         — transfer files (base64)",
            "create_folder                       — create a new folder",
            "delete_path / move_path / copy_path — file management",
            "create_shared_link                  — generate a public share link",
            "list_shared_links                   — view existing shared links",
        ],
    },
}

_ALL_TOOLS = ["gmail", "calendar", "github", "slack", "jira", "dropbox", "trello"]


def build_system_prompt(connected_tools: list[str]) -> str:
    """Build a system prompt that accurately reflects the user's connected tools."""

    if connected_tools:
        active_lines: list[str] = []
        for tool in connected_tools:
            info = _TOOL_DESCRIPTIONS.get(tool)
            if info:
                active_lines.append(f"\n### {info['name']}")
                for cap in info["capabilities"]:
                    active_lines.append(f"  - {cap}")
            else:
                active_lines.append(f"\n### {tool.title()} (connected)")
        active_block = "\n".join(active_lines)
        connected_section = (
            "# Connected tools — you can act on these RIGHT NOW\n"
            "When the user asks about them, your routing system hands off to the "
            "right specialist agent automatically. If asked what you can do, list "
            "these tools and capabilities accurately. If the user asks something general, give them a short answer.\n"
            + active_block
            + "\n"
        )
    else:
        connected_section = (
            "# Connected tools\n"
            "The user has not connected any tools yet. If they ask about email, "
            "calendar, or other integrations, guide them to **Settings → Connections**.\n"
        )

    not_connected = [t for t in _ALL_TOOLS if t not in connected_tools]
    if not_connected:
        nc_list = ", ".join(t.title() for t in not_connected)
        upcoming_section = (
            f"# Not yet connected\n{nc_list} — user can connect via "
            "**Settings → Connections**. Mention them only if relevant.\n"
        )
    else:
        upcoming_section = "# All supported tools are connected!\n"

    return f"""\
You are **ByteOps**, an intelligent AI productivity assistant for modern \
knowledge workers and development teams.

# Personality
- Professional yet warm — a trusted colleague, not a corporate bot.
- Concise but thorough — never pad answers; one-liners when appropriate.
- Honest — if something isn't possible, say so clearly.
- Action-oriented — show results, don't narrate what you're about to do.

# Core capabilities (always available)
- Answer questions on any topic using built-in knowledge.
- Draft emails, summarise documents, write or explain code.
- Help plan projects, break down tasks, analyse data.
- Guide users through ByteOps features.

{connected_section}
{upcoming_section}
{RESPONSE_FORMAT}
- When listing capabilities, be accurate — never invent tools that aren't listed above.
"""


async def stream_general_response(
    history: list[dict],
    queue: asyncio.Queue,
    connected_tools: list[str] | None = None,
) -> str:
    """Stream a Claude response for general (non-tool) conversation.

    Pushes individual text delta strings into `queue` as they arrive.
    Pushes `None` sentinel when the stream is complete.
    Returns the full assembled response text.
    """
    client = _get_claude_client()
    system_prompt = build_system_prompt(connected_tools or [])

    # Claude takes system as a separate param; filter history to user/assistant only
    messages = [m for m in history if m["role"] in ("user", "assistant")]

    full_text = ""

    # Retry up to 3 times on rate-limit
    for attempt in range(3):
        try:
            async with client.messages.stream(
                model=CLAUDE_MODEL,
                max_tokens=8192,
                system=system_prompt,
                messages=messages,
            ) as stream:
                async for text in stream.text_stream:
                    full_text += text
                    await queue.put(text)
            break  # success — exit retry loop
        except anthropic.RateLimitError:
            if attempt < 2:
                await asyncio.sleep(20)
            else:
                raise

    await queue.put(None)  # sentinel — consumer should stop after this
    return full_text
