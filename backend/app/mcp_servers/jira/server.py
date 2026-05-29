"""Jira MCP Server.

Exposes Jira Cloud REST API capabilities as MCP tools via FastMCP.
Credentials are injected via environment variables by the Jira Agent
when spawning this server as a stdio subprocess.

Tools (Reading):
  - list_projects      — list Jira projects
  - search_issues      — search issues via JQL
  - get_issue          — get full details of an issue
  - get_transitions    — list available workflow transitions for an issue
  - list_boards        — list Jira Agile boards
  - list_sprints       — list sprints for a board
  - get_current_user   — get the authenticated user's profile

Tools (Writing):
  - create_issue       — create a new issue
  - update_issue       — update an existing issue
  - transition_issue   — move an issue to a new workflow state
  - add_comment        — add a comment to an issue
  - update_comment     — update an existing comment
  - delete_comment     — delete a comment from an issue
  - assign_issue       — assign an issue to a user
"""

from __future__ import annotations

import os
import sys
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


_JIRA_API_VERSION = "rest/api/3"
_JIRA_AGILE_VERSION = "rest/agile/1.0"


def _adf_body(text: str) -> dict:
    """Wrap plain text in Atlassian Document Format (ADF)."""
    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": text}],
            }
        ],
    }


class JiraClient:
    """Thin synchronous wrapper around the Jira Cloud REST API."""

    def __init__(self, token: str, cloud_id: str, cloud_url: str = "") -> None:
        self.token = token
        self.cloud_id = cloud_id
        self.cloud_url = cloud_url.rstrip("/")
        self._base = f"https://api.atlassian.com/ex/jira/{cloud_id}/{_JIRA_API_VERSION}"
        self._agile_base = f"https://api.atlassian.com/ex/jira/{cloud_id}/{_JIRA_AGILE_VERSION}"
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: dict | None = None, agile: bool = False) -> Any:
        base = self._agile_base if agile else self._base
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(f"{base}{path}", headers=self._headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, body: dict, agile: bool = False) -> Any:
        base = self._agile_base if agile else self._base
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(f"{base}{path}", headers=self._headers, json=body)
            resp.raise_for_status()
            return resp.json()

    def _put(self, path: str, body: dict, agile: bool = False) -> Any:
        base = self._agile_base if agile else self._base
        with httpx.Client(timeout=30.0) as client:
            resp = client.put(f"{base}{path}", headers=self._headers, json=body)
            resp.raise_for_status()
            # Jira PUT /issue returns 204 No Content; return empty dict in that case
            if resp.status_code == 204 or not resp.content:
                return {}
            return resp.json()

    def _delete(self, path: str, agile: bool = False) -> Any:
        base = self._agile_base if agile else self._base
        with httpx.Client(timeout=30.0) as client:
            resp = client.delete(f"{base}{path}", headers=self._headers)
            resp.raise_for_status()
            return {}

    # ── Reading ───────────────────────────────────────────────────────────────

    def list_projects(self, max_results: int = 50) -> list[dict]:
        """List Jira projects accessible to the authenticated user."""
        data = self._get("/project/search", {"maxResults": max_results})
        projects = data.get("values", data) if isinstance(data, dict) else data
        return [
            {
                "id": p.get("id", ""),
                "key": p.get("key", ""),
                "name": p.get("name", ""),
                "type": p.get("projectTypeKey", ""),
                "lead": (p.get("lead") or {}).get("displayName", ""),
            }
            for p in projects
        ]

    def search_issues(
        self,
        jql: str,
        max_results: int = 20,
        fields: list[str] | None = None,
    ) -> list[dict]:
        """Search for issues using JQL."""
        default_fields = [
            "summary", "status", "assignee", "priority",
            "issuetype", "created", "updated",
        ]
        payload: dict[str, Any] = {
            "jql": jql,
            "maxResults": max_results,
            "fields": fields if fields else default_fields,
        }
        data = self._post("/issue/search", payload)
        issues = data.get("issues", [])
        return [
            {
                "id": i.get("id", ""),
                "key": i.get("key", ""),
                "summary": (i.get("fields") or {}).get("summary", ""),
                "status": ((i.get("fields") or {}).get("status") or {}).get("name", ""),
                "assignee": (
                    ((i.get("fields") or {}).get("assignee") or {}).get("displayName", "Unassigned")
                ),
                "priority": (
                    ((i.get("fields") or {}).get("priority") or {}).get("name", "")
                ),
                "type": (
                    ((i.get("fields") or {}).get("issuetype") or {}).get("name", "")
                ),
                "created": (i.get("fields") or {}).get("created", ""),
                "updated": (i.get("fields") or {}).get("updated", ""),
            }
            for i in issues
        ]

    def get_issue(self, issue_key: str) -> dict:
        """Get full details of a single Jira issue."""
        i = self._get(f"/issue/{issue_key}", {"expand": "renderedFields"})
        fields = i.get("fields") or {}
        comments = (fields.get("comment") or {}).get("total", 0)
        return {
            "id": i.get("id", ""),
            "key": i.get("key", ""),
            "summary": fields.get("summary", ""),
            "description": fields.get("description") or "",
            "status": (fields.get("status") or {}).get("name", ""),
            "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
            "reporter": (fields.get("reporter") or {}).get("displayName", ""),
            "priority": (fields.get("priority") or {}).get("name", ""),
            "type": (fields.get("issuetype") or {}).get("name", ""),
            "labels": fields.get("labels", []),
            "components": [c.get("name", "") for c in fields.get("components", [])],
            "comments_count": comments,
            "created": fields.get("created", ""),
            "updated": fields.get("updated", ""),
        }

    def create_issue(
        self,
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str = "Medium",
        assignee_account_id: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Create a new Jira issue."""
        fields: dict[str, Any] = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
            "priority": {"name": priority},
        }
        if description:
            fields["description"] = _adf_body(description)
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        if labels:
            fields["labels"] = labels

        data = self._post("/issue", {"fields": fields})
        return {
            "id": data.get("id", ""),
            "key": data.get("key", ""),
            "url": f"{self.cloud_url}/browse/{data.get('key', '')}" if self.cloud_url else f"https://api.atlassian.com/ex/jira/{self.cloud_id}/browse/{data.get('key', '')}",
        }

    def update_issue(
        self,
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        assignee_account_id: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Update an existing Jira issue."""
        fields: dict[str, Any] = {}
        if summary is not None:
            fields["summary"] = summary
        if description is not None:
            fields["description"] = _adf_body(description)
        if priority is not None:
            fields["priority"] = {"name": priority}
        if assignee_account_id is not None:
            fields["assignee"] = {"accountId": assignee_account_id}
        if labels is not None:
            fields["labels"] = labels

        self._put(f"/issue/{issue_key}", {"fields": fields})
        return {"key": issue_key, "status": "updated"}

    def transition_issue(self, issue_key: str, transition_name: str) -> dict:
        """Transition an issue to a new workflow state by name."""
        transitions = self.get_transitions(issue_key)
        matched = next(
            (t for t in transitions if t["name"].lower() == transition_name.lower()),
            None,
        )
        if not matched:
            available = [t["name"] for t in transitions]
            raise ValueError(
                f"Transition '{transition_name}' not found. "
                f"Available: {available}"
            )
        self._post(
            f"/issue/{issue_key}/transitions",
            {"transition": {"id": matched["id"]}},
        )
        return {"key": issue_key, "transitioned_to": transition_name, "status": "ok"}

    def add_comment(self, issue_key: str, body_text: str) -> dict:
        """Add a comment to a Jira issue."""
        data = self._post(
            f"/issue/{issue_key}/comment",
            {"body": _adf_body(body_text)},
        )
        return {
            "id": data.get("id", ""),
            "issue_key": issue_key,
            "author": (data.get("author") or {}).get("displayName", ""),
            "created": data.get("created", ""),
        }

    def update_comment(self, issue_key: str, comment_id: str, body_text: str) -> dict:
        """Update an existing comment on a Jira issue."""
        data = self._put(
            f"/issue/{issue_key}/comment/{comment_id}",
            {"body": _adf_body(body_text)},
        )
        return {
            "id": data.get("id", comment_id),
            "issue_key": issue_key,
            "updated": data.get("updated", ""),
        }

    def delete_comment(self, issue_key: str, comment_id: str) -> dict:
        """Delete a comment from a Jira issue."""
        self._delete(f"/issue/{issue_key}/comment/{comment_id}")
        return {"status": "deleted", "comment_id": comment_id, "issue_key": issue_key}

    def get_transitions(self, issue_key: str) -> list[dict]:
        """Return the available workflow transitions for an issue."""
        data = self._get(f"/issue/{issue_key}/transitions")
        return [
            {"id": t.get("id", ""), "name": t.get("name", "")}
            for t in data.get("transitions", [])
        ]

    def assign_issue(self, issue_key: str, account_id: str) -> dict:
        """Assign a Jira issue to a user by their account ID."""
        self._put(f"/issue/{issue_key}/assignee", {"accountId": account_id})
        return {"key": issue_key, "assignee_account_id": account_id, "status": "assigned"}

    def list_boards(self, max_results: int = 20) -> list[dict]:
        """List Jira Agile boards."""
        data = self._get("/board", {"maxResults": max_results}, agile=True)
        boards = data.get("values", [])
        return [
            {
                "id": b.get("id", ""),
                "name": b.get("name", ""),
                "type": b.get("type", ""),
                "project_key": (b.get("location") or {}).get("projectKey", ""),
            }
            for b in boards
        ]

    def list_sprints(self, board_id: int, state: str = "active") -> list[dict]:
        """List sprints for a Jira Agile board."""
        data = self._get(
            f"/board/{board_id}/sprint",
            {"state": state},
            agile=True,
        )
        sprints = data.get("values", [])
        return [
            {
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "state": s.get("state", ""),
                "start_date": s.get("startDate", ""),
                "end_date": s.get("endDate", ""),
                "goal": s.get("goal", ""),
            }
            for s in sprints
        ]

    def get_current_user(self) -> dict:
        """Get the authenticated user's Jira profile."""
        data = self._get("/myself")
        return {
            "account_id": data.get("accountId", ""),
            "display_name": data.get("displayName", ""),
            "email": data.get("emailAddress", ""),
            "active": data.get("active", True),
            "timezone": data.get("timeZone", ""),
        }


def create_jira_server(token: str, cloud_id: str, cloud_url: str = "") -> FastMCP:
    """Create and return a FastMCP instance with all Jira tools wired up."""
    server = FastMCP("ByteOps Jira Agent")
    client = JiraClient(token=token, cloud_id=cloud_id, cloud_url=cloud_url)

    # ── Reading tools ─────────────────────────────────────────────────────────

    @server.tool()
    def list_projects(max_results: int = 50) -> list[dict]:
        """List Jira projects accessible to the authenticated user.
        Returns id, key, name, type, and lead for each project.
        """
        return client.list_projects(max_results=max_results)

    @server.tool()
    def search_issues(
        jql: str,
        max_results: int = 20,
        fields: list[str] | None = None,
    ) -> list[dict]:
        """Search for Jira issues using JQL (Jira Query Language).
        Args:
          jql: JQL query string (e.g. 'project = MYPROJ AND status = \"In Progress\"')
          max_results: maximum number of issues to return (default 20)
          fields: optional list of field names to include; defaults to common fields
        Returns id, key, summary, status, assignee, priority, type, created, updated.
        Examples:
          - 'assignee = currentUser()'
          - 'project = KEY AND sprint in openSprints()'
          - 'status changed to Done after -7d'
        """
        return client.search_issues(jql=jql, max_results=max_results, fields=fields)

    @server.tool()
    def get_issue(issue_key: str) -> dict:
        """Get full details of a single Jira issue, including description, comments count,
        labels, and components.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
        """
        return client.get_issue(issue_key=issue_key)

    @server.tool()
    def get_transitions(issue_key: str) -> list[dict]:
        """List the available workflow transitions for a Jira issue.
        Call this before transition_issue to see valid state names.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
        Returns a list of {id, name} for each available transition.
        """
        return client.get_transitions(issue_key=issue_key)

    @server.tool()
    def list_boards(max_results: int = 20) -> list[dict]:
        """List Jira Agile boards accessible to the authenticated user.
        Returns id, name, type, and project_key for each board.
        """
        return client.list_boards(max_results=max_results)

    @server.tool()
    def list_sprints(board_id: int, state: str = "active") -> list[dict]:
        """List sprints for a Jira Agile board.
        Args:
          board_id: the numeric board ID (from list_boards)
          state: sprint state filter — 'active', 'future', 'closed', or 'active,future'
        Returns id, name, state, start_date, end_date, and goal.
        """
        return client.list_sprints(board_id=board_id, state=state)

    @server.tool()
    def get_current_user() -> dict:
        """Get the authenticated Jira user's profile.
        Returns account_id, display_name, email, active status, and timezone.
        Useful for obtaining your own account_id to use in assign_issue or JQL.
        """
        return client.get_current_user()

    # ── Writing tools ─────────────────────────────────────────────────────────

    @server.tool()
    def create_issue(
        project_key: str,
        summary: str,
        description: str = "",
        issue_type: str = "Task",
        priority: str = "Medium",
        assignee_account_id: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Create a new Jira issue.
        Args:
          project_key: the project key (e.g. 'MYPROJ') — use list_projects to find it
          summary: issue title / summary
          description: optional plain-text description
          issue_type: e.g. 'Task', 'Bug', 'Story', 'Epic' (default: 'Task')
          priority: 'Highest', 'High', 'Medium', 'Low', 'Lowest' (default: 'Medium')
          assignee_account_id: optional Jira account ID of the assignee
          labels: optional list of label strings
        Returns the created issue's id, key, and URL.
        IMPORTANT: Always confirm project, summary, and type with the user unless already specified.
        """
        return client.create_issue(
            project_key=project_key,
            summary=summary,
            description=description,
            issue_type=issue_type,
            priority=priority,
            assignee_account_id=assignee_account_id,
            labels=labels,
        )

    @server.tool()
    def update_issue(
        issue_key: str,
        summary: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        assignee_account_id: str | None = None,
        labels: list[str] | None = None,
    ) -> dict:
        """Update fields on an existing Jira issue. Only provided fields are changed.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
          summary: new summary/title (optional)
          description: new plain-text description (optional)
          priority: new priority name (optional)
          assignee_account_id: new assignee's Jira account ID (optional)
          labels: new list of labels — replaces existing labels (optional)
        Returns {key, status: 'updated'}.
        """
        return client.update_issue(
            issue_key=issue_key,
            summary=summary,
            description=description,
            priority=priority,
            assignee_account_id=assignee_account_id,
            labels=labels,
        )

    @server.tool()
    def transition_issue(issue_key: str, transition_name: str) -> dict:
        """Move a Jira issue to a new workflow state.
        IMPORTANT: First call get_transitions to see the valid state names for this issue.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
          transition_name: the exact transition name (case-insensitive) from get_transitions
        Returns {key, transitioned_to, status: 'ok'}.
        """
        return client.transition_issue(issue_key=issue_key, transition_name=transition_name)

    @server.tool()
    def add_comment(issue_key: str, body_text: str) -> dict:
        """Add a comment to a Jira issue.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
          body_text: plain-text comment content
        Returns the comment id, issue_key, author, and created timestamp.
        """
        return client.add_comment(issue_key=issue_key, body_text=body_text)

    @server.tool()
    def update_comment(issue_key: str, comment_id: str, body_text: str) -> dict:
        """Update an existing comment on a Jira issue.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
          comment_id: the comment ID (visible in add_comment response or issue details)
          body_text: new plain-text content for the comment
        Returns the comment id, issue_key, and updated timestamp.
        """
        return client.update_comment(
            issue_key=issue_key, comment_id=comment_id, body_text=body_text
        )

    @server.tool()
    def delete_comment(issue_key: str, comment_id: str) -> dict:
        """Delete a comment from a Jira issue.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
          comment_id: the comment ID to delete
        Returns {status: 'deleted', comment_id, issue_key}.
        IMPORTANT: Confirm with the user before deleting; this action is irreversible.
        """
        return client.delete_comment(issue_key=issue_key, comment_id=comment_id)

    @server.tool()
    def assign_issue(issue_key: str, account_id: str) -> dict:
        """Assign a Jira issue to a user.
        Args:
          issue_key: the issue key (e.g. 'PROJ-123')
          account_id: the Jira account ID of the user to assign
                      (use get_current_user to get your own account_id)
        Returns {key, assignee_account_id, status: 'assigned'}.
        """
        return client.assign_issue(issue_key=issue_key, account_id=account_id)

    return server


if __name__ == "__main__":
    token = os.environ.get("JIRA_ACCESS_TOKEN", "")
    cloud_id = os.environ.get("JIRA_CLOUD_ID", "")
    cloud_url = os.environ.get("JIRA_CLOUD_URL", "")

    if not token:
        print("ERROR: JIRA_ACCESS_TOKEN env var is required.", file=sys.stderr, flush=True)
        sys.exit(1)
    if not cloud_id:
        print("ERROR: JIRA_CLOUD_ID env var is required.", file=sys.stderr, flush=True)
        sys.exit(1)

    server = create_jira_server(token=token, cloud_id=cloud_id, cloud_url=cloud_url)
    server.run()
