"""Drive REAL agent runs by sending varied prompts through /api/chat.

Accumulates genuine telemetry (real tools, real model). Nothing synthetic is
written to the DB — only the choice of prompts is scripted.

Usage:
  python scripts/drive_usage.py --token "<clerk_jwt>" --rounds 10 --base http://localhost:8000

Get a Clerk JWT from browser devtools (Authorization header on any API call)
while signed in to the running frontend.
"""

from __future__ import annotations

import argparse
import time

import httpx

PROMPTS = [
    # ── Gmail ──
    "Summarize my latest 5 emails.",
    "Do I have any unread important emails?",
    "Find emails from my manager about the project.",
    "Search my inbox for anything about invoices.",
    "Show me emails I haven't replied to.",
    "Any emails with attachments this week?",
    "Draft a reply to my most recent email.",
    "Find the latest newsletter in my inbox.",
    "Who emailed me the most this week?",
    "Summarize the thread with the longest conversation.",
    # ── Calendar ──
    "What's on my calendar this week?",
    "Any meetings tomorrow morning?",
    "Do I have any conflicts in my schedule today?",
    "When is my next free 1-hour slot?",
    "List all my meetings for Friday.",
    "What's my first meeting tomorrow?",
    "Summarize my week's calendar.",
    # ── GitHub ──
    "List my open GitHub pull requests.",
    "Any failing CI checks on my repos?",
    "Show recent commits on my main project.",
    "Are there any PRs waiting for my review?",
    "What issues are assigned to me on GitHub?",
    "Show the most recently updated repository.",
    # ── Slack ──
    "Catch me up on my unread Slack messages.",
    "Any direct messages I missed today?",
    "What's the latest in my main Slack channel?",
    "Did anyone mention me on Slack today?",
    "Summarize unread messages across my channels.",
    # ── Jira ──
    "What Jira tickets are assigned to me?",
    "Any blocked tickets in the current sprint?",
    "Show my highest priority open ticket.",
    "What's the status of the current sprint?",
    "List tickets I created this week.",
    # ── Dropbox ──
    "What files were shared with me in Dropbox recently?",
    "Show my most recently modified files.",
    "Search Dropbox for the latest report.",
    # ── Cross-tool / multi-step (most valuable — longer action sequences) ──
    "Summarize today's activity across all my tools.",
    "Catch me up: emails, calendar, and Slack for today.",
    "Prepare me for my next meeting using my emails and calendar.",
    "What needs my attention across Gmail, Jira, and GitHub?",
    "Give me a morning briefing from all my connected tools.",
    "Find anything urgent across my inbox and Slack.",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--token", required=True, help="Clerk JWT")
    parser.add_argument("--base", default="http://localhost:8000")
    parser.add_argument("--rounds", type=int, default=5, help="passes over the prompt list")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between calls")
    args = parser.parse_args()

    headers = {"Authorization": f"Bearer {args.token}", "Content-Type": "application/json"}
    sent = 0
    for r in range(args.rounds):
        for prompt in PROMPTS:
            body = {"message": f"{prompt} (run {r + 1})"}
            try:
                with httpx.stream(
                    "POST", f"{args.base}/api/chat", headers=headers, json=body, timeout=120
                ) as resp:
                    for _ in resp.iter_lines():
                        pass  # drain the SSE stream so the run completes
                sent += 1
                print(f"[{sent}] ok: {prompt[:48]}")
            except Exception as exc:  # noqa: BLE001
                print(f"  failed: {prompt[:40]} -> {exc}")
            time.sleep(args.delay)
    print(f"Done. Triggered {sent} real runs.")


if __name__ == "__main__":
    main()
