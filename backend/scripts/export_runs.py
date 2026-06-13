"""Export real agent runs from the DB into JSONL token sequences for training.

Usage: python scripts/export_runs.py --out data/runs.jsonl
Run sequences are labeled by agent_runs.data_label (normal/redteam/unlabeled).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.anomaly.tokenizer import run_to_tokens  # noqa: E402


def run_record_to_sequence(record: dict) -> dict:
    return {
        "run_id": record["id"],
        "label": record.get("data_label", "unlabeled"),
        "tokens": run_to_tokens(record.get("steps", [])),
    }


async def _export(out_path: Path) -> int:
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.core.database import async_session_factory
    from app.models.agent_run import AgentRun
    from app.services.agent_runtime import serialize_agent_run

    async with async_session_factory() as session:
        result = await session.execute(
            select(AgentRun).options(selectinload(AgentRun.steps)).order_by(AgentRun.created_at)
        )
        runs = result.scalars().all()

    count = 0
    with out_path.open("w", encoding="utf-8") as f:
        for run in runs:
            seq = run_record_to_sequence(serialize_agent_run(run))
            if not seq["tokens"]:
                continue
            f.write(json.dumps(seq) + "\n")
            count += 1
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="data/runs.jsonl")
    args = parser.parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    n = asyncio.run(_export(out_path))
    print(f"Exported {n} run sequences to {out_path}")


if __name__ == "__main__":
    main()
