"""Gmail MCP Server.

Exposes Gmail API capabilities as MCP tools via FastMCP.

Credentials are injected as environment variables by the Gmail Agent when
spawning this server as a stdio subprocess — one instance per user request.

Tools (Reading):
  - list_emails          — fetch recent emails with metadata
  - search_emails        — Gmail search query (is:unread, from:boss, etc.)
  - get_email_content    — full decoded body of a specific email by ID
  - get_thread           — full conversation thread by thread ID
  - list_labels          — list all Gmail labels for the user

Tools (Writing):
  - send_email           — compose and send a new email
  - reply_to_email       — reply to an existing thread
  - forward_email        — forward an email to another recipient
  - create_draft         — save a draft without sending
  - send_draft           — send a previously saved draft
"""

from __future__ import annotations

import base64
import email as email_lib
import os
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from mcp.server.fastmcp import FastMCP
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build


# ── Helpers ───────────────────────────────────────────────────────────────────

def _b64url_decode(data: str) -> bytes:
    """Decode a base64url-encoded string (Gmail API uses this everywhere)."""
    # Pad to a multiple of 4
    data += "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data)


def _extract_body(payload: dict) -> str:
    """Recursively walk a Gmail message payload and extract plain text."""
    mime_type = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data")

    # Direct plain-text part
    if mime_type == "text/plain" and body_data:
        return _b64url_decode(body_data).decode("utf-8", errors="replace")

    # HTML fallback — strip tags
    if mime_type == "text/html" and body_data:
        raw_html = _b64url_decode(body_data).decode("utf-8", errors="replace")
        return re.sub(r"<[^>]+>", "", raw_html)

    # Multipart — recurse into parts
    parts = payload.get("parts", [])
    for part in parts:
        text = _extract_body(part)
        if text:
            return text

    return ""


def _headers_dict(payload: dict) -> dict[str, str]:
    """Return a {name.lower(): value} dict of all message headers."""
    return {
        h["name"].lower(): h["value"]
        for h in payload.get("headers", [])
    }


def _make_message(to: str, subject: str, body: str,
                  from_addr: str = "me") -> dict:
    """Build a base64url-encoded RFC 2822 message ready for Gmail API."""
    msg = MIMEMultipart()
    msg["to"] = to
    msg["from"] = from_addr
    msg["subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw}


def _make_reply(original: dict, body: str) -> dict:
    """Build a reply message that threads correctly in Gmail."""
    payload = original.get("payload", {})
    hdrs = _headers_dict(payload)

    msg = MIMEMultipart()
    msg["to"] = hdrs.get("from", "")
    msg["subject"] = "Re: " + hdrs.get("subject", "")
    msg["in-reply-to"] = hdrs.get("message-id", "")
    msg["references"] = hdrs.get("message-id", "")
    msg.attach(MIMEText(body, "plain"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    return {"raw": raw, "threadId": original.get("threadId")}


# ── GmailClient ───────────────────────────────────────────────────────────────

class GmailClient:
    """Thin wrapper around the Google Gmail API v1 service.

    Handles token refresh automatically using the refresh_token + client
    credentials passed in from the Gmail Agent.
    """

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        # Refresh proactively if expired and we have a refresh token
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        self.service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    # ── Reading ──────────────────────────────────────────────────────────────

    def list_messages(self, query: str = "", max_results: int = 10) -> list[dict]:
        """Return a list of message summaries matching the query."""
        results = (
            self.service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        messages = results.get("messages", [])
        if not messages:
            return []

        summaries = []
        for msg in messages:
            detail = (
                self.service.users()
                .messages()
                .get(
                    userId="me",
                    id=msg["id"],
                    format="metadata",
                    metadataHeaders=["Subject", "From", "Date", "To"],
                )
                .execute()
            )
            hdrs = _headers_dict(detail.get("payload", {}))
            summaries.append(
                {
                    "id": detail["id"],
                    "threadId": detail["threadId"],
                    "snippet": detail.get("snippet", ""),
                    "subject": hdrs.get("subject", "(no subject)"),
                    "from": hdrs.get("from", "unknown"),
                    "to": hdrs.get("to", ""),
                    "date": hdrs.get("date", ""),
                }
            )
        return summaries

    def get_message(self, message_id: str) -> dict:
        """Return full parsed content of a single message."""
        msg = (
            self.service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        payload = msg.get("payload", {})
        hdrs = _headers_dict(payload)
        body = _extract_body(payload)
        return {
            "id": msg["id"],
            "threadId": msg["threadId"],
            "subject": hdrs.get("subject", "(no subject)"),
            "from": hdrs.get("from", "unknown"),
            "to": hdrs.get("to", ""),
            "date": hdrs.get("date", ""),
            "body": body or msg.get("snippet", "(no body)"),
        }

    def get_thread(self, thread_id: str) -> list[dict]:
        """Return all messages in a thread, in order."""
        thread = (
            self.service.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )
        results = []
        for msg in thread.get("messages", []):
            payload = msg.get("payload", {})
            hdrs = _headers_dict(payload)
            body = _extract_body(payload)
            results.append(
                {
                    "id": msg["id"],
                    "from": hdrs.get("from", "unknown"),
                    "date": hdrs.get("date", ""),
                    "body": body or msg.get("snippet", ""),
                }
            )
        return results

    def list_labels(self) -> list[dict]:
        """Return all labels visible to the authenticated user."""
        resp = self.service.users().labels().list(userId="me").execute()
        return [
            {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "")}
            for lbl in resp.get("labels", [])
        ]

    # ── Writing ──────────────────────────────────────────────────────────────

    def send(self, message_body: dict) -> dict:
        """Send a message (or draft send). Returns the sent message metadata."""
        sent = (
            self.service.users()
            .messages()
            .send(userId="me", body=message_body)
            .execute()
        )
        return {"id": sent["id"], "threadId": sent.get("threadId")}

    def create_draft(self, message_body: dict) -> dict:
        """Save a draft. Returns the draft ID."""
        draft = (
            self.service.users()
            .drafts()
            .create(userId="me", body={"message": message_body})
            .execute()
        )
        return {"draft_id": draft["id"]}

    def send_draft(self, draft_id: str) -> dict:
        """Send an existing draft by draft ID."""
        sent = (
            self.service.users()
            .drafts()
            .send(userId="me", body={"id": draft_id})
            .execute()
        )
        return {"id": sent["id"], "threadId": sent.get("threadId")}

    def trash_message(self, message_id: str) -> dict:
        """Move a message to Trash."""
        result = (
            self.service.users()
            .messages()
            .trash(userId="me", id=message_id)
            .execute()
        )
        return {"id": result["id"], "status": "trashed"}

    def delete_message_permanently(self, message_id: str) -> dict:
        """Permanently delete a message — cannot be undone."""
        self.service.users().messages().delete(userId="me", id=message_id).execute()
        return {"id": message_id, "status": "permanently_deleted"}

    def modify_labels(self, message_id: str,
                      add_labels: list[str] | None = None,
                      remove_labels: list[str] | None = None) -> dict:
        """Add or remove label IDs on a message."""
        body: dict = {}
        if add_labels:
            body["addLabelIds"] = add_labels
        if remove_labels:
            body["removeLabelIds"] = remove_labels
        result = (
            self.service.users()
            .messages()
            .modify(userId="me", id=message_id, body=body)
            .execute()
        )
        return {"id": result["id"], "labelIds": result.get("labelIds", [])}


# ── FastMCP Setup ─────────────────────────────────────────────────────────────

def create_gmail_server(
    access_token: str,
    refresh_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> FastMCP:
    """Create and return a FastMCP instance with all Gmail tools wired up."""

    server = FastMCP("ByteOps Gmail Agent")
    client = GmailClient(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
    )

    # ── Reading tools ─────────────────────────────────────────────────────────

    @server.tool()
    def list_emails(max_results: int = 10) -> list[dict]:
        """List the user's most recent emails from their inbox.
        Returns subject, sender, date, and a short snippet for each.
        Use this to give the user an overview of recent activity.
        """
        return client.list_messages(query="-in:sent -in:draft", max_results=max_results)

    @server.tool()
    def search_emails(query: str, max_results: int = 10) -> list[dict]:
        """Search the user's emails using Gmail search operators.
        Examples: 'is:unread', 'from:boss@company.com', 'subject:invoice',
        'after:2024/01/01', 'has:attachment', 'label:important'.
        Returns matching emails with subject, sender, date, and snippet.
        """
        return client.list_messages(query=query, max_results=max_results)

    @server.tool()
    def get_email_content(message_id: str) -> dict:
        """Get the full body content of a specific email by its message ID.
        Use this after list_emails or search_emails to read the full text.
        Returns subject, sender, to, date, and the full decoded body.
        """
        return client.get_message(message_id)

    @server.tool()
    def get_thread(thread_id: str) -> list[dict]:
        """Get all messages in an email thread/conversation by thread ID.
        Use this to see the full back-and-forth of a conversation.
        Returns a list of messages in chronological order with sender and body.
        """
        return client.get_thread(thread_id)

    @server.tool()
    def list_labels() -> list[dict]:
        """List all Gmail labels belonging to the user.
        Returns label id, display name, and type (system or user-created).
        Useful for discovering labels to use in search queries.
        """
        return client.list_labels()

    # ── Writing tools ─────────────────────────────────────────────────────────

    @server.tool()
    def send_email(to: str, subject: str, body: str) -> dict:
        """Compose and send a new email immediately.
        Args:
          to: recipient email address (e.g. 'alice@example.com')
          subject: email subject line
          body: plain text body of the email
        Returns the ID and thread ID of the sent message.
        IMPORTANT: Always confirm the recipient and content with the user before calling this.
        """
        msg = _make_message(to=to, subject=subject, body=body)
        return client.send(msg)

    @server.tool()
    def reply_to_email(message_id: str, body: str) -> dict:
        """Reply to an existing email thread.
        Args:
          message_id: the ID of the message to reply to (from list_emails or search_emails)
          body: the text of your reply
        Automatically threads correctly with In-Reply-To and References headers.
        IMPORTANT: Always confirm the reply content with the user before calling this.
        """
        original = (
            client.service.users()
            .messages()
            .get(userId="me", id=message_id, format="metadata",
                 metadataHeaders=["Subject", "From", "Message-ID"])
            .execute()
        )
        msg = _make_reply(original, body)
        return client.send(msg)

    @server.tool()
    def forward_email(message_id: str, to: str, note: str = "") -> dict:
        """Forward an existing email to one or more recipients.
        Args:
          message_id: the ID of the email to forward
          to: recipient address(es), comma-separated
          note: optional note to prepend above the forwarded content
        IMPORTANT: Always confirm before forwarding sensitive information.
        """
        original = client.get_message(message_id)
        fwd_body = ""
        if note:
            fwd_body = f"{note}\n\n"
        fwd_body += (
            f"---------- Forwarded message ----------\n"
            f"From: {original['from']}\n"
            f"Date: {original['date']}\n"
            f"Subject: {original['subject']}\n\n"
            f"{original['body']}"
        )
        msg = _make_message(
            to=to,
            subject="Fwd: " + original["subject"],
            body=fwd_body,
        )
        return client.send(msg)

    @server.tool()
    def create_draft(to: str, subject: str, body: str) -> dict:
        """Save an email as a draft without sending it.
        Args:
          to: recipient email address
          subject: email subject line
          body: plain text body
        Returns the draft_id which can later be passed to send_draft.
        """
        msg = _make_message(to=to, subject=subject, body=body)
        return client.create_draft(msg)

    @server.tool()
    def send_draft(draft_id: str) -> dict:
        """Send a previously saved draft email.
        Args:
          draft_id: the ID returned by create_draft
        Returns the ID of the sent message.
        """
        return client.send_draft(draft_id)

    @server.tool()
    def trash_email(message_id: str) -> dict:
        """Move an email to Trash (recoverable for 30 days).
        Args:
          message_id: the ID of the email to trash (from list_emails or search_emails)
        Returns confirmation with the message ID.
        IMPORTANT: Confirm with the user before trashing.
        """
        return client.trash_message(message_id)

    @server.tool()
    def delete_email_permanently(message_id: str) -> dict:
        """Permanently and irreversibly delete an email. Cannot be undone.
        Args:
          message_id: the ID of the email to delete permanently
        IMPORTANT: This is irreversible. Always confirm explicitly with the user.
        Prefer trash_email unless the user specifically requests permanent deletion.
        """
        return client.delete_message_permanently(message_id)

    @server.tool()
    def mark_as_read(message_id: str) -> dict:
        """Mark an email as read (removes the UNREAD label).
        Args:
          message_id: the ID of the email to mark as read
        """
        return client.modify_labels(message_id, remove_labels=["UNREAD"])

    @server.tool()
    def mark_as_unread(message_id: str) -> dict:
        """Mark an email as unread (adds the UNREAD label).
        Args:
          message_id: the ID of the email to mark as unread
        """
        return client.modify_labels(message_id, add_labels=["UNREAD"])

    @server.tool()
    def apply_label(message_id: str, label_id: str) -> dict:
        """Apply a label to an email. Use list_labels to find label IDs.
        Args:
          message_id: the ID of the email
          label_id: the label ID to apply (e.g. 'IMPORTANT', 'STARRED', or a custom label ID)
        """
        return client.modify_labels(message_id, add_labels=[label_id])

    @server.tool()
    def remove_label(message_id: str, label_id: str) -> dict:
        """Remove a label from an email.
        Args:
          message_id: the ID of the email
          label_id: the label ID to remove
        """
        return client.modify_labels(message_id, remove_labels=[label_id])

    return server


# ── Entry point (stdio subprocess mode) ──────────────────────────────────────

if __name__ == "__main__":
    access_token = os.environ.get("GMAIL_ACCESS_TOKEN", "")
    refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN")
    client_id = os.environ.get("GMAIL_CLIENT_ID")
    client_secret = os.environ.get("GMAIL_CLIENT_SECRET")

    if not access_token:
        import sys
        print("ERROR: GMAIL_ACCESS_TOKEN env var is required.", file=sys.stderr, flush=True)
        sys.exit(1)

    server = create_gmail_server(
        access_token=access_token,
        refresh_token=refresh_token,
        client_id=client_id,
        client_secret=client_secret,
    )
    server.run()
