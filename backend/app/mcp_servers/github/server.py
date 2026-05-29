"""GitHub MCP Server.

Exposes GitHub REST API capabilities as MCP tools via FastMCP.
The GitHub personal access token is injected via environment variable
by the GitHub Agent when spawning this server as a stdio subprocess.

Tools (Reading):
  - list_repos         — list user's repositories
  - list_prs           — list pull requests for a repo
  - list_issues        — list issues for a repo
  - get_pr             — get full details of a pull request
  - get_issue          — get full details of an issue
  - list_notifications — list GitHub notifications

Tools (Writing):
  - create_repo        — create a new repository
  - create_issue       — create an issue in a repo
  - create_pr          — open a pull request
  - comment_on_issue   — add a comment to an issue or PR
  - close_issue        — close an open issue
"""

from __future__ import annotations

import os
from typing import Any

import httpx
from mcp.server.fastmcp import FastMCP


_GITHUB_API = "https://api.github.com"
_HEADERS_BASE = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubClient:
    """Thin synchronous wrapper around the GitHub REST API."""

    def __init__(self, token: str) -> None:
        self.headers = {**_HEADERS_BASE, "Authorization": f"Bearer {token}"}

    def _get(self, path: str, params: dict | None = None) -> Any:
        with httpx.Client(timeout=20.0) as client:
            resp = client.get(f"{_GITHUB_API}{path}", headers=self.headers, params=params)
            resp.raise_for_status()
            return resp.json()

    def _post(self, path: str, body: dict) -> Any:
        with httpx.Client(timeout=20.0) as client:
            resp = client.post(f"{_GITHUB_API}{path}", headers=self.headers, json=body)
            resp.raise_for_status()
            return resp.json()

    def _patch(self, path: str, body: dict) -> Any:
        with httpx.Client(timeout=20.0) as client:
            resp = client.patch(f"{_GITHUB_API}{path}", headers=self.headers, json=body)
            resp.raise_for_status()
            return resp.json()

    # ── Reading ───────────────────────────────────────────────────────────────

    def list_repos(self, max_results: int = 10) -> list[dict]:
        """List authenticated user's repositories, most recently pushed first."""
        repos = self._get("/user/repos", {"sort": "pushed", "per_page": max_results})
        return [
            {
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description") or "",
                "private": r["private"],
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language") or "",
                "open_issues": r.get("open_issues_count", 0),
                "url": r["html_url"],
            }
            for r in repos
        ]

    def list_prs(self, repo: str, state: str = "open", max_results: int = 10) -> list[dict]:
        """List pull requests for a repository."""
        prs = self._get(f"/repos/{repo}/pulls", {"state": state, "per_page": max_results})
        return [
            {
                "number": pr["number"],
                "title": pr["title"],
                "author": pr["user"]["login"],
                "state": pr["state"],
                "draft": pr.get("draft", False),
                "created_at": pr["created_at"],
                "updated_at": pr["updated_at"],
                "url": pr["html_url"],
                "body": (pr.get("body") or "")[:500],
            }
            for pr in prs
        ]

    def list_issues(self, repo: str, state: str = "open", max_results: int = 10) -> list[dict]:
        """List issues for a repository (excludes PRs)."""
        issues = self._get(
            f"/repos/{repo}/issues",
            {"state": state, "per_page": max_results, "pulls": "false"},
        )
        return [
            {
                "number": i["number"],
                "title": i["title"],
                "author": i["user"]["login"],
                "state": i["state"],
                "labels": [lbl["name"] for lbl in i.get("labels", [])],
                "created_at": i["created_at"],
                "updated_at": i["updated_at"],
                "url": i["html_url"],
            }
            for i in issues
            if "pull_request" not in i
        ]

    def get_pr(self, repo: str, pr_number: int) -> dict:
        """Get full details of a single pull request."""
        pr = self._get(f"/repos/{repo}/pulls/{pr_number}")
        return {
            "number": pr["number"],
            "title": pr["title"],
            "author": pr["user"]["login"],
            "state": pr["state"],
            "draft": pr.get("draft", False),
            "body": pr.get("body") or "",
            "changed_files": pr.get("changed_files", 0),
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
            "created_at": pr["created_at"],
            "updated_at": pr["updated_at"],
            "url": pr["html_url"],
        }

    def get_issue(self, repo: str, issue_number: int) -> dict:
        """Get full details of a single issue."""
        issue = self._get(f"/repos/{repo}/issues/{issue_number}")
        return {
            "number": issue["number"],
            "title": issue["title"],
            "author": issue["user"]["login"],
            "state": issue["state"],
            "body": issue.get("body") or "",
            "labels": [lbl["name"] for lbl in issue.get("labels", [])],
            "created_at": issue["created_at"],
            "updated_at": issue["updated_at"],
            "url": issue["html_url"],
        }

    def list_notifications(self, max_results: int = 20) -> list[dict]:
        """List GitHub notifications for the authenticated user."""
        notifs = self._get("/notifications", {"per_page": max_results})
        return [
            {
                "id": n["id"],
                "type": n["subject"]["type"],
                "title": n["subject"]["title"],
                "repo": n["repository"]["full_name"],
                "reason": n["reason"],
                "unread": n["unread"],
                "updated_at": n["updated_at"],
            }
            for n in notifs
        ]

    # ── Writing ───────────────────────────────────────────────────────────────

    def create_repo(
        self,
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
    ) -> dict:
        """Create a new repository for the authenticated user."""
        data = self._post("/user/repos", {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init,
        })
        return {
            "name": data["name"],
            "full_name": data["full_name"],
            "description": data.get("description") or "",
            "private": data["private"],
            "url": data["html_url"],
            "clone_url": data["clone_url"],
        }

    def create_issue(
        self,
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> dict:
        """Create a new issue in a repository."""
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        data = self._post(f"/repos/{repo}/issues", payload)
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "url": data["html_url"],
        }

    def create_pr(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> dict:
        """Open a pull request from head branch into base branch."""
        data = self._post(f"/repos/{repo}/pulls", {
            "title": title,
            "body": body,
            "head": head,
            "base": base,
            "draft": draft,
        })
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "url": data["html_url"],
        }

    def comment_on_issue(self, repo: str, issue_number: int, body: str) -> dict:
        """Add a comment to an issue or pull request."""
        data = self._post(f"/repos/{repo}/issues/{issue_number}/comments", {"body": body})
        return {
            "id": data["id"],
            "body": data["body"],
            "url": data["html_url"],
        }

    def close_issue(self, repo: str, issue_number: int) -> dict:
        """Close an open issue."""
        data = self._patch(f"/repos/{repo}/issues/{issue_number}", {"state": "closed"})
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "url": data["html_url"],
        }

    def update_issue(
        self,
        repo: str,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict:
        """Update an existing issue."""
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if state is not None:
            payload["state"] = state
        if labels is not None:
            payload["labels"] = labels
        if assignees is not None:
            payload["assignees"] = assignees
        data = self._patch(f"/repos/{repo}/issues/{issue_number}", payload)
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "url": data["html_url"],
        }

    def merge_pr(self, repo: str, pr_number: int,
                 commit_title: str = "", merge_method: str = "merge") -> dict:
        """Merge a pull request."""
        payload: dict = {"merge_method": merge_method}
        if commit_title:
            payload["commit_title"] = commit_title
        data = self._post(f"/repos/{repo}/pulls/{pr_number}/merge", payload)
        return {
            "merged": data.get("merged", False),
            "sha": data.get("sha", ""),
            "message": data.get("message", ""),
        }

    def close_pr(self, repo: str, pr_number: int) -> dict:
        """Close a pull request without merging."""
        data = self._patch(f"/repos/{repo}/pulls/{pr_number}", {"state": "closed"})
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "url": data["html_url"],
        }

    def update_pr(
        self,
        repo: str,
        pr_number: int,
        title: str | None = None,
        body: str | None = None,
        base: str | None = None,
    ) -> dict:
        """Update a pull request's title, body, or target base branch."""
        payload: dict = {}
        if title is not None:
            payload["title"] = title
        if body is not None:
            payload["body"] = body
        if base is not None:
            payload["base"] = base
        data = self._patch(f"/repos/{repo}/pulls/{pr_number}", payload)
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "url": data["html_url"],
        }


def create_github_server(token: str) -> FastMCP:
    """Create and return a FastMCP instance with all GitHub tools wired up."""
    server = FastMCP("ByteOps GitHub Agent")
    client = GitHubClient(token=token)

    # ── Reading tools ─────────────────────────────────────────────────────────

    @server.tool()
    def list_repos(max_results: int = 10) -> list[dict]:
        """List the authenticated user's GitHub repositories, sorted by recent activity.
        Returns name, full_name, description, stars, language, open issues count, and URL.
        """
        return client.list_repos(max_results=max_results)

    @server.tool()
    def list_prs(repo: str, state: str = "open", max_results: int = 10) -> list[dict]:
        """List pull requests for a GitHub repository.
        Args:
          repo: repository in 'owner/repo' format (e.g. 'torvalds/linux')
          state: 'open', 'closed', or 'all' (default: 'open')
          max_results: maximum number of PRs to return (default 10)
        """
        return client.list_prs(repo=repo, state=state, max_results=max_results)

    @server.tool()
    def list_issues(repo: str, state: str = "open", max_results: int = 10) -> list[dict]:
        """List issues for a GitHub repository (pull requests are excluded).
        Args:
          repo: repository in 'owner/repo' format
          state: 'open', 'closed', or 'all' (default: 'open')
          max_results: maximum number of issues to return (default 10)
        """
        return client.list_issues(repo=repo, state=state, max_results=max_results)

    @server.tool()
    def get_pr(repo: str, pr_number: int) -> dict:
        """Get the full details of a single pull request.
        Args:
          repo: repository in 'owner/repo' format
          pr_number: the pull request number
        """
        return client.get_pr(repo=repo, pr_number=pr_number)

    @server.tool()
    def get_issue(repo: str, issue_number: int) -> dict:
        """Get the full details of a single issue.
        Args:
          repo: repository in 'owner/repo' format
          issue_number: the issue number
        """
        return client.get_issue(repo=repo, issue_number=issue_number)

    @server.tool()
    def list_notifications(max_results: int = 20) -> list[dict]:
        """List GitHub notifications (mentions, review requests, assignments, etc.)
        for the authenticated user across all repositories.
        """
        return client.list_notifications(max_results=max_results)

    # ── Writing tools ─────────────────────────────────────────────────────────

    @server.tool()
    def create_repo(
        name: str,
        description: str = "",
        private: bool = False,
        auto_init: bool = True,
    ) -> dict:
        """Create a new GitHub repository for the authenticated user.
        Args:
          name: repository name (e.g. 'my-new-project')
          description: optional repository description
          private: True for private repo, False for public (default: False)
          auto_init: initialize with a README (default: True)
        Returns name, full_name, URL, and clone_url.
        IMPORTANT: Always confirm name and visibility with the user before creating.
        """
        return client.create_repo(
            name=name,
            description=description,
            private=private,
            auto_init=auto_init,
        )

    @server.tool()
    def create_issue(
        repo: str,
        title: str,
        body: str = "",
        labels: list[str] | None = None,
    ) -> dict:
        """Create a new issue in a GitHub repository.
        Args:
          repo: repository in 'owner/repo' format
          title: issue title
          body: issue description / body text
          labels: optional list of label names to apply
        Returns the issue number, title, state, and URL.
        IMPORTANT: Confirm with the user before creating.
        """
        return client.create_issue(repo=repo, title=title, body=body, labels=labels)

    @server.tool()
    def create_pr(
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
        draft: bool = False,
    ) -> dict:
        """Open a pull request from a head branch into a base branch.
        Args:
          repo: repository in 'owner/repo' format
          title: PR title
          body: PR description
          head: source branch name (e.g. 'feature/login')
          base: target branch name (default: 'main')
          draft: create as a draft PR (default: False)
        Returns the PR number, title, state, and URL.
        IMPORTANT: Confirm details with the user before creating.
        """
        return client.create_pr(
            repo=repo, title=title, body=body, head=head, base=base, draft=draft
        )

    @server.tool()
    def comment_on_issue(repo: str, issue_number: int, body: str) -> dict:
        """Add a comment to a GitHub issue or pull request.
        Args:
          repo: repository in 'owner/repo' format
          issue_number: issue or PR number
          body: the comment text (Markdown supported)
        Returns the comment id and URL.
        """
        return client.comment_on_issue(repo=repo, issue_number=issue_number, body=body)

    @server.tool()
    def close_issue(repo: str, issue_number: int) -> dict:
        """Close an open GitHub issue.
        Args:
          repo: repository in 'owner/repo' format
          issue_number: the issue number to close
        IMPORTANT: Confirm with the user before closing.
        """
        return client.close_issue(repo=repo, issue_number=issue_number)

    @server.tool()
    def update_issue(
        repo: str,
        issue_number: int,
        title: str | None = None,
        body: str | None = None,
        state: str | None = None,
        labels: list[str] | None = None,
        assignees: list[str] | None = None,
    ) -> dict:
        """Update an existing GitHub issue. Only provided fields are changed.
        Args:
          repo: repository in 'owner/repo' format
          issue_number: the issue number to update
          title: new title (omit to keep existing)
          body: new description (omit to keep existing)
          state: 'open' or 'closed' (omit to keep existing)
          labels: full replacement list of label names (omit to keep existing)
          assignees: full replacement list of GitHub usernames (omit to keep existing)
        IMPORTANT: Confirm changes with the user before updating.
        """
        return client.update_issue(repo=repo, issue_number=issue_number,
                                   title=title, body=body, state=state,
                                   labels=labels, assignees=assignees)

    @server.tool()
    def merge_pr(
        repo: str,
        pr_number: int,
        commit_title: str = "",
        merge_method: str = "merge",
    ) -> dict:
        """Merge an open pull request.
        Args:
          repo: repository in 'owner/repo' format
          pr_number: the pull request number
          commit_title: optional custom merge commit title
          merge_method: 'merge' (default), 'squash', or 'rebase'
        Returns merged status, commit SHA, and message.
        IMPORTANT: Confirm with the user before merging.
        """
        return client.merge_pr(repo=repo, pr_number=pr_number,
                                commit_title=commit_title, merge_method=merge_method)

    @server.tool()
    def close_pr(repo: str, pr_number: int) -> dict:
        """Close a pull request without merging.
        Args:
          repo: repository in 'owner/repo' format
          pr_number: the pull request number to close
        IMPORTANT: Confirm with the user before closing.
        """
        return client.close_pr(repo=repo, pr_number=pr_number)

    @server.tool()
    def update_pr(
        repo: str,
        pr_number: int,
        title: str | None = None,
        body: str | None = None,
        base: str | None = None,
    ) -> dict:
        """Update a pull request's title, description, or base branch.
        Args:
          repo: repository in 'owner/repo' format
          pr_number: the pull request number
          title: new title (omit to keep existing)
          body: new description (omit to keep existing)
          base: new target base branch (omit to keep existing)
        IMPORTANT: Confirm changes with the user before updating.
        """
        return client.update_pr(repo=repo, pr_number=pr_number,
                                 title=title, body=body, base=base)

    return server


if __name__ == "__main__":
    import sys
    token = os.environ.get("GITHUB_ACCESS_TOKEN", "")
    if not token:
        print("ERROR: GITHUB_ACCESS_TOKEN env var is required.", file=sys.stderr, flush=True)
        sys.exit(1)

    server = create_github_server(token=token)
    server.run()
