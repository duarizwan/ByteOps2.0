"""Label agent runs as red-team (anomalous) so the evaluator can measure detection.

The self-supervised LSTM trains on NORMAL runs and never needs labels. But to
*measure* how well any detector catches anomalies, you need a held-out set of
runs you know are bad. Those are the 'redteam' runs.

Usage:
  python scripts/label_redteam.py --list                 # show recent runs to choose from
  python scripts/label_redteam.py <run_id> [<run_id> ...] # mark these runs as redteam
  python scripts/label_redteam.py --unlabel <run_id> ...  # revert to 'unlabeled'
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import select, update

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import async_session_factory  # noqa: E402
from app.models.agent_run import AgentRun  # noqa: E402


async def _list() -> None:
    async with async_session_factory() as s:
        rows = (
            await s.execute(select(AgentRun).order_by(AgentRun.created_at.desc()).limit(50))
        ).scalars().all()
        print(f"{'run_id':38}  {'label':10}  {'intent':10}  created")
        print("-" * 80)
        for r in rows:
            print(f"{str(r.id):38}  {r.data_label:10}  {(r.intent or ''):10}  {str(r.created_at)[:19]}")
        print(f"\n{len(rows)} most recent runs. Copy the run_id(s) of anomalous ones and run:")
        print("  python scripts/label_redteam.py <run_id> <run_id> ...")


async def _set_label(ids: list[str], label: str) -> None:
    async with async_session_factory() as s:
        res = await s.execute(
            update(AgentRun).where(AgentRun.id.in_(ids)).values(data_label=label)
        )
        await s.commit()
        print(f"Set data_label='{label}' on {res.rowcount} run(s).")


async def _auto_label_rejected() -> None:
    """Auto-label every run that contains a rejected risky action (a real
    red-team attempt you blocked at the approval gate) as 'redteam'."""
    from sqlalchemy import text
    async with async_session_factory() as s:
        ids = [row[0] for row in (await s.execute(text(
            "SELECT DISTINCT st.run_id FROM agent_run_steps st "
            "WHERE st.name LIKE 'reject:%' OR st.status = 'rejected'"
        ))).all()]
        if not ids:
            print("No rejected-attempt runs found. (Reject a risky action at the approval gate first.)")
            return
        res = await s.execute(
            update(AgentRun).where(AgentRun.id.in_(ids)).values(data_label="redteam")
        )
        await s.commit()
        print(f"Auto-labeled {res.rowcount} rejected-attempt run(s) as redteam.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*", help="run IDs to label as redteam")
    parser.add_argument("--list", action="store_true", help="list recent runs")
    parser.add_argument("--auto-rejected", action="store_true",
                        help="auto-label all runs with a rejected risky action as redteam")
    parser.add_argument("--unlabel", action="store_true", help="revert given IDs to 'unlabeled'")
    args = parser.parse_args()

    if args.auto_rejected:
        asyncio.run(_auto_label_rejected())
    elif args.list:
        asyncio.run(_list())
    elif args.ids:
        asyncio.run(_set_label(args.ids, "unlabeled" if args.unlabel else "redteam"))
    else:
        print("Nothing to do. Use --list to see runs, or pass run IDs to label.")


if __name__ == "__main__":
    main()
