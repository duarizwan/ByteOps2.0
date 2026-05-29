"""Slack MCP Server.

Exposes Slack Web API capabilities as MCP tools via FastMCP.
The Slack bot token is injected via the SLACK_BOT_TOKEN environment variable
by the Slack Agent when spawning this server as a stdio subprocess.

Tools (Reading):
  - list_channels        — list public and private channels
  - get_channel_messages — retrieve recent messages from a channel
  - get_thread_replies   — retrieve replies in a thread
  - list_users           — list workspace members
  - get_user_info        — get details for a specific user
  - list_my_channels     — list channels the bot/user is a member of

Tools (Writing):
  - send_message         — post a message to a channel or thread
  - update_message       — edit an existing message
  - delete_message       — delete a message
  - send_dm              — open a DM and send a message to a user
  - add_reaction         — add an emoji reaction to a message
  - remove_reaction      — remove an emoji reaction from a message
"""

from __future__ import annotations

import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackClient:
    """Thin synchronous wrapper around the Slack Web API using slack-sdk."""

    def __init__(self, token: str) -> None:
        self._client = WebClient(token=token)

    # ── Reading ───────────────────────────────────────────────────────────────

    def list_channels(self, limit: int = 100) -> list[dict]:
        """List public and private channels in the workspace.

        Returns id, name, is_private, member_count, topic, and purpose for each channel.
        Requires scopes: channels:read, groups:read
        """
        response = self._client.conversations_list(
            types="public_channel,private_channel",
            limit=limit,
        )
        channels = response.get("channels", [])
        return [
            {
                "id": c["id"],
                "name": c.get("name", ""),
                "is_private": c.get("is_private", False),
                "member_count": c.get("num_members", 0),
                "topic": c.get("topic", {}).get("value", ""),
                "purpose": c.get("purpose", {}).get("value", ""),
            }
            for c in channels
        ]

    def get_channel_messages(self, channel_id: str, limit: int = 20) -> list[dict]:
        """Retrieve recent messages from a channel.

        Returns ts, user, text, thread_ts, and reply_count for each message.
        Requires scopes: channels:history, groups:history
        """
        response = self._client.conversations_history(
            channel=channel_id,
            limit=limit,
        )
        messages = response.get("messages", [])
        return [
            {
                "ts": m.get("ts", ""),
                "user": m.get("user", m.get("bot_id", "")),
                "text": m.get("text", ""),
                "thread_ts": m.get("thread_ts", ""),
                "reply_count": m.get("reply_count", 0),
            }
            for m in messages
        ]

    def get_thread_replies(self, channel_id: str, thread_ts: str) -> list[dict]:
        """Retrieve all replies in a message thread.

        Returns ts, user, text, and thread_ts for each reply.
        Requires scopes: channels:history, groups:history
        """
        response = self._client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
        )
        messages = response.get("messages", [])
        return [
            {
                "ts": m.get("ts", ""),
                "user": m.get("user", m.get("bot_id", "")),
                "text": m.get("text", ""),
                "thread_ts": m.get("thread_ts", ""),
            }
            for m in messages
        ]

    def list_users(self, limit: int = 100) -> list[dict]:
        """List members of the Slack workspace.

        Returns id, name, real_name, email, and is_bot for each user.
        Requires scopes: users:read, users:read.email
        """
        response = self._client.users_list(limit=limit)
        members = response.get("members", [])
        return [
            {
                "id": u["id"],
                "name": u.get("name", ""),
                "real_name": u.get("real_name", ""),
                "email": u.get("profile", {}).get("email", ""),
                "is_bot": u.get("is_bot", False),
            }
            for u in members
            if not u.get("deleted", False)
        ]

    def get_user_info(self, user_id: str) -> dict:
        """Get detailed info for a specific Slack user.

        Requires scopes: users:read, users:read.email
        """
        response = self._client.users_info(user=user_id)
        u = response.get("user", {})
        return {
            "id": u.get("id", ""),
            "name": u.get("name", ""),
            "real_name": u.get("real_name", ""),
            "email": u.get("profile", {}).get("email", ""),
            "title": u.get("profile", {}).get("title", ""),
            "is_bot": u.get("is_bot", False),
            "is_admin": u.get("is_admin", False),
            "tz": u.get("tz", ""),
        }

    def list_channels_i_member_of(self) -> list[dict]:
        """List channels the authenticated bot/user is a member of.

        Requires scopes: channels:read, groups:read
        """
        response = self._client.users_conversations(
            types="public_channel,private_channel",
            exclude_archived=True,
        )
        channels = response.get("channels", [])
        return [
            {
                "id": c["id"],
                "name": c.get("name", ""),
                "is_private": c.get("is_private", False),
                "member_count": c.get("num_members", 0),
            }
            for c in channels
        ]

    def search_messages(self, query: str, limit: int = 20) -> list[dict]:
        """Search messages across the workspace.

        NOTE: This method requires a user token with the search:read scope,
        not a bot token. If a bot token is provided it will raise a SlackApiError
        with not_allowed_token_type; in that case this method returns an empty list
        with a note instead of raising.

        Requires scopes: search:read (user token only)
        """
        try:
            response = self._client.search_messages(query=query, count=limit)
            matches = response.get("messages", {}).get("matches", [])
            return [
                {
                    "ts": m.get("ts", ""),
                    "channel_id": m.get("channel", {}).get("id", ""),
                    "channel_name": m.get("channel", {}).get("name", ""),
                    "user": m.get("user", ""),
                    "text": m.get("text", ""),
                    "permalink": m.get("permalink", ""),
                }
                for m in matches
            ]
        except SlackApiError as e:
            # search.messages is only available with user tokens
            return [{"error": str(e), "note": "search_messages requires a user token with search:read scope"}]

    # ── Writing ───────────────────────────────────────────────────────────────

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
    ) -> dict:
        """Post a message to a channel, optionally as a thread reply.

        Returns ts and channel.
        Requires scopes: chat:write
        """
        kwargs: dict[str, Any] = {"channel": channel_id, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        response = self._client.chat_postMessage(**kwargs)
        return {
            "ts": response.get("ts", ""),
            "channel": response.get("channel", ""),
        }

    def update_message(self, channel_id: str, ts: str, text: str) -> dict:
        """Edit an existing message.

        Returns ts and channel.
        Requires scopes: chat:write
        """
        response = self._client.chat_update(channel=channel_id, ts=ts, text=text)
        return {
            "ts": response.get("ts", ""),
            "channel": response.get("channel", ""),
        }

    def delete_message(self, channel_id: str, ts: str) -> dict:
        """Delete a message from a channel.

        Returns ok (bool).
        Requires scopes: chat:write
        """
        response = self._client.chat_delete(channel=channel_id, ts=ts)
        return {"ok": response.get("ok", False)}

    def open_dm(self, user_id: str) -> str:
        """Open a direct message channel with a user and return the channel ID.

        Requires scopes: im:write
        """
        response = self._client.conversations_open(users=[user_id])
        channel = response.get("channel", {})
        return channel.get("id", "")

    def add_reaction(self, channel_id: str, ts: str, emoji: str) -> dict:
        """Add an emoji reaction to a message.

        The emoji name should NOT include colons (e.g. 'thumbsup' not ':thumbsup:').
        Requires scopes: reactions:write
        """
        response = self._client.reactions_add(
            channel=channel_id,
            timestamp=ts,
            name=emoji.strip(":"),
        )
        return {"ok": response.get("ok", False)}

    def remove_reaction(self, channel_id: str, ts: str, emoji: str) -> dict:
        """Remove an emoji reaction from a message.

        The emoji name should NOT include colons (e.g. 'thumbsup' not ':thumbsup:').
        Requires scopes: reactions:write
        """
        response = self._client.reactions_remove(
            channel=channel_id,
            timestamp=ts,
            name=emoji.strip(":"),
        )
        return {"ok": response.get("ok", False)}


def create_slack_server(token: str) -> FastMCP:
    """Create and return a FastMCP instance with all Slack tools wired up."""
    server = FastMCP("ByteOps Slack Agent")
    client = SlackClient(token=token)

    # ── Reading tools ─────────────────────────────────────────────────────────

    @server.tool()
    def list_channels(limit: int = 100) -> list[dict]:
        """List public and private channels in the Slack workspace.

        Returns id, name, is_private, member_count, topic, and purpose for each channel.
        Requires bot scopes: channels:read, groups:read

        Args:
          limit: maximum number of channels to return (default 100)
        """
        return client.list_channels(limit=limit)

    @server.tool()
    def get_channel_messages(channel_id: str, limit: int = 20) -> list[dict]:
        """Retrieve the most recent messages from a Slack channel.

        Returns ts, user, text, thread_ts, and reply_count for each message.
        Requires bot scopes: channels:history, groups:history

        Args:
          channel_id: the Slack channel ID (e.g. 'C01234567')
          limit: maximum number of messages to return (default 20)
        """
        return client.get_channel_messages(channel_id=channel_id, limit=limit)

    @server.tool()
    def get_thread_replies(channel_id: str, thread_ts: str) -> list[dict]:
        """Retrieve all replies in a Slack message thread.

        Returns ts, user, text, and thread_ts for each message in the thread.
        Requires bot scopes: channels:history, groups:history

        Args:
          channel_id: the Slack channel ID containing the thread
          thread_ts: the timestamp of the parent (root) message
        """
        return client.get_thread_replies(channel_id=channel_id, thread_ts=thread_ts)

    @server.tool()
    def list_users(limit: int = 100) -> list[dict]:
        """List members of the Slack workspace (bots excluded from label but included in data).

        Returns id, name, real_name, email, and is_bot for each non-deleted user.
        Requires bot scopes: users:read, users:read.email

        Args:
          limit: maximum number of users to return (default 100)
        """
        return client.list_users(limit=limit)

    @server.tool()
    def get_user_info(user_id: str) -> dict:
        """Get detailed profile information for a specific Slack user.

        Returns id, name, real_name, email, title, is_bot, is_admin, and timezone.
        Requires bot scopes: users:read, users:read.email

        Args:
          user_id: the Slack user ID (e.g. 'U01234567')
        """
        return client.get_user_info(user_id=user_id)

    @server.tool()
    def list_my_channels() -> list[dict]:
        """List all Slack channels that the authenticated bot or user is a member of.

        Returns id, name, is_private, and member_count for each channel.
        Requires bot scopes: channels:read, groups:read
        """
        return client.list_channels_i_member_of()

    # ── Writing tools ─────────────────────────────────────────────────────────

    @server.tool()
    def send_message(
        channel_id: str,
        text: str,
        thread_ts: str = "",
    ) -> dict:
        """Post a message to a Slack channel or thread.

        Returns ts (message timestamp) and channel.
        Requires bot scope: chat:write

        Args:
          channel_id: the Slack channel ID (e.g. 'C01234567')
          text: the message text (Markdown-like formatting supported)
          thread_ts: optional parent message timestamp to reply in a thread
        IMPORTANT: Confirm content and recipient with the user before calling unless already confirmed.
        """
        return client.send_message(
            channel_id=channel_id,
            text=text,
            thread_ts=thread_ts or None,
        )

    @server.tool()
    def update_message(channel_id: str, ts: str, text: str) -> dict:
        """Edit (update) an existing Slack message.

        Returns ts and channel.
        Requires bot scope: chat:write

        Args:
          channel_id: the Slack channel ID where the message lives
          ts: the timestamp of the message to edit
          text: the new message text
        IMPORTANT: Always confirm the new content and target message with the user before calling.
        """
        return client.update_message(channel_id=channel_id, ts=ts, text=text)

    @server.tool()
    def delete_message(channel_id: str, ts: str) -> dict:
        """Delete a message from a Slack channel.

        Returns ok (bool indicating success).
        Requires bot scope: chat:write

        Args:
          channel_id: the Slack channel ID where the message lives
          ts: the timestamp of the message to delete
        IMPORTANT: Always confirm with the user before deleting a message.
        """
        return client.delete_message(channel_id=channel_id, ts=ts)

    @server.tool()
    def send_dm(user_id: str, text: str) -> dict:
        """Open a direct message channel with a Slack user and send them a message.

        Internally calls conversations_open then chat_postMessage.
        Returns ts and channel.
        Requires bot scopes: im:write, chat:write

        Args:
          user_id: the Slack user ID to DM (e.g. 'U01234567')
          text: the message text to send
        IMPORTANT: Confirm content and recipient with the user before calling unless already confirmed.
        """
        channel_id = client.open_dm(user_id=user_id)
        return client.send_message(channel_id=channel_id, text=text)

    @server.tool()
    def add_reaction(channel_id: str, ts: str, emoji: str) -> dict:
        """Add an emoji reaction to a Slack message.

        Returns ok (bool indicating success).
        Requires bot scope: reactions:write

        Args:
          channel_id: the Slack channel ID containing the message
          ts: the timestamp of the message to react to
          emoji: emoji name WITHOUT colons (e.g. 'thumbsup', 'heart', '+1')
        """
        return client.add_reaction(channel_id=channel_id, ts=ts, emoji=emoji)

    @server.tool()
    def remove_reaction(channel_id: str, ts: str, emoji: str) -> dict:
        """Remove an emoji reaction from a Slack message.

        Returns ok (bool indicating success).
        Requires bot scope: reactions:write

        Args:
          channel_id: the Slack channel ID containing the message
          ts: the timestamp of the message
          emoji: emoji name WITHOUT colons (e.g. 'thumbsup', 'heart', '+1')
        """
        return client.remove_reaction(channel_id=channel_id, ts=ts, emoji=emoji)

    return server


if __name__ == "__main__":
    token = os.environ.get("SLACK_BOT_TOKEN", "")
    if not token:
        print("ERROR: SLACK_BOT_TOKEN env var is required.", file=sys.stderr, flush=True)
        sys.exit(1)

    server = create_slack_server(token=token)
    server.run()
