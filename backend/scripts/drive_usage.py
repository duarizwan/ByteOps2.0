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
    "Summarize my latest 5 emails.",
    "Do I have any unread important emails?",
    "What's on my calendar this week?",
    "Any meetings tomorrow morning?",
    "Find emails from my manager about the project.",
    "List my open GitHub pull requests.",
    "Any failing CI checks on my repos?",
    "Show recent commits on my main project.",
    "What Jira tickets are assigned to me?",
    "Any blocked tickets in the current sprint?",
    "Catch me up on my unread Slack messages.",
    "Any direct messages I missed today?",
    "Draft a reply to my most recent email.",
    "What files were shared with me in Dropbox recently?",
    "Summarize today's activity across my tools.",
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
