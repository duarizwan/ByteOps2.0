"""Evaluate and COMPARE the three anomaly detectors on real ByteOps telemetry.

Produces the headline result for the Deep Learning course report:
a side-by-side comparison of
  1. Next-action LSTM        (self-supervised deep learning — the contribution)
  2. Isolation Forest        (classical ML baseline)
  3. LLM black-box monitor   (frontier baseline, Storf et al. 2026)
using partial AUROC at low false-positive rate (FPR < 0.2) and F1.

Usage:
  python scripts/evaluate_detectors.py --data data/runs.jsonl            # all three
  python scripts/evaluate_detectors.py --data data/runs.jsonl --no-llm   # skip LLM calls

Inputs: data/runs.jsonl produced by scripts/export_runs.py. Sequences labeled
'normal'/'unlabeled' are negatives; 'redteam' are positives.

Outputs:
  - prints a markdown comparison table
  - outputs/comparison.md  (paste into the report)
  - logs all metrics to MLflow (experiment 'byteops-anomaly-eval'); view with `mlflow ui`

Honest note: with few runs the numbers are weak — that is expected and should be
reported as a data-scaling limitation, not hidden.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

import numpy as np

from app.anomaly.tokenizer import PAD, build_vocab, encode_tokens

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"


# ── Metrics ──────────────────────────────────────────────────────────────────

def partial_auroc(labels: np.ndarray, scores: np.ndarray, max_fpr: float = 0.2) -> float:
    """Partial AUROC over FPR in [0, max_fpr], normalized so perfect=1.0, random=max_fpr/...

    Follows the metric used by Storf et al. (2026): integrate the ROC curve only
    over the low-FPR region that matters for human oversight, then normalize by
    the window width so perfect = 1.0.
    """
    order = np.argsort(-scores)
    labels = labels[order]
    P = labels.sum()
    N = len(labels) - P
    if P == 0 or N == 0:
        return float("nan")
    tpr = np.cumsum(labels) / P
    fpr = np.cumsum(1 - labels) / N
    tpr = np.concatenate([[0.0], tpr])
    fpr = np.concatenate([[0.0], fpr])
    area = 0.0
    for i in range(1, len(fpr)):
        if fpr[i - 1] >= max_fpr:
            break
        x0, x1 = fpr[i - 1], min(fpr[i], max_fpr)
        if x1 > x0:
            area += (x1 - x0) * (tpr[i] + tpr[i - 1]) / 2.0
    return float(area / max_fpr)


def best_f1(labels: np.ndarray, scores: np.ndarray) -> tuple[float, float, float, float]:
    """Return (f1, precision, recall, threshold) at the score threshold maximizing F1."""
    best = (0.0, 0.0, 0.0, 0.0)
    for thr in np.unique(scores):
        pred = (scores >= thr).astype(int)
        tp = int(((pred == 1) & (labels == 1)).sum())
        fp = int(((pred == 1) & (labels == 0)).sum())
        fn = int(((pred == 0) & (labels == 1)).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        if f1 > best[0]:
            best = (f1, prec, rec, float(thr))
    return best


# ── Detectors ────────────────────────────────────────────────────────────────

def lstm_scores(train, eval_items, vocab, max_len, epochs, hidden, embed, seed):
    """Train the next-action LSTM on `train` (normal), return session NLL for eval_items."""
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    vocab_size = len(vocab)

    def enc(items):
        return torch.tensor([encode_tokens(s["tokens"], vocab, max_len) for s in items], dtype=torch.long)

    class NextActionLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(vocab_size, embed, padding_idx=vocab[PAD])
            self.lstm = nn.LSTM(embed, hidden, batch_first=True)
            self.head = nn.Linear(hidden, vocab_size)

        def forward(self, x):
            out, _ = self.lstm(self.embed(x))
            return self.head(out)

    model = NextActionLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=vocab[PAD])
    xb = enc(train)
    model.train()
    for _ in range(epochs):
        opt.zero_grad()
        logits = model(xb[:, :-1])
        loss = loss_fn(logits.reshape(-1, vocab_size), xb[:, 1:].reshape(-1))
        loss.backward()
        opt.step()

    model.eval()
    out = []
    with torch.no_grad():
        x = enc(eval_items)
        logp = torch.log_softmax(model(x), dim=-1)
        for b in range(x.shape[0]):
            nlls = []
            for t in range(1, max_len):
                tok = x[b, t].item()
                if tok == vocab[PAD]:
                    break
                nlls.append(-logp[b, t - 1, tok].item())
            out.append(max(nlls) if nlls else 0.0)
    return np.array(out)


def iso_scores(train, eval_items, seed):
    from sklearn.ensemble import IsolationForest

    def feats(items):
        rows = []
        for s in items:
            toks = s["tokens"]; n = len(toks) or 1
            ext = sum(1 for t in toks if "external_send" in t or "destructive" in t)
            rows.append([n, ext / n, len(set(toks)) / n])
        return np.array(rows) if items else np.zeros((0, 3))

    iso = IsolationForest(n_estimators=200, contamination=0.2, random_state=seed)
    iso.fit(feats(train))
    # Higher = more anomalous: negate the signed decision function.
    return -iso.decision_function(feats(eval_items))


async def llm_scores(eval_items):
    """Score each eval run 1-10 with the LLM black-box monitor (from token text)."""
    from app.anomaly.llm_monitor import score_run_llm

    out = []
    for s in eval_items:
        # Reconstruct a readable trajectory from tokens for the action-only monitor.
        steps = []
        for tok in s["tokens"]:
            parts = tok.split("|")
            step_type = parts[0] if parts else "step"
            name = parts[1] if len(parts) > 1 else tok
            status = parts[2] if len(parts) > 2 else "completed"
            steps.append({"step_type": step_type, "name": name, "status": status})
        res = await score_run_llm(steps)
        out.append(float(res["score"]) if res else 5.0)
    return np.array(out)


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import mlflow

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/runs.jsonl")
    parser.add_argument("--max-len", type=int, default=12)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--hidden", type=int, default=48)
    parser.add_argument("--embed", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-llm", action="store_true", help="skip the LLM monitor (no API calls)")
    args = parser.parse_args()

    seqs = [json.loads(line) for line in Path(args.data).read_text(encoding="utf-8").splitlines() if line.strip()]
    normal = [s for s in seqs if s["label"] in ("normal", "unlabeled")]
    redteam = [s for s in seqs if s["label"] == "redteam"]

    if not redteam:
        print("ERROR: no 'redteam' runs in the data — cannot evaluate detection. "
              "Label some real out-of-policy runs first (see the plan, Task 9).")
        return
    if len(normal) < 4:
        print(f"WARNING: only {len(normal)} normal runs — metrics will be very noisy.")

    rng = np.random.default_rng(args.seed)
    idx = rng.permutation(len(normal))
    cut = max(1, int(0.7 * len(normal)))
    train = [normal[i] for i in idx[:cut]]
    val_normal = [normal[i] for i in idx[cut:]] or [normal[idx[0]]]

    # Eval set: held-out normal (label 0) + redteam (label 1)
    eval_items = val_normal + redteam
    labels = np.array([0] * len(val_normal) + [1] * len(redteam))

    vocab = build_vocab([s["tokens"] for s in train])

    detectors: dict[str, np.ndarray] = {}
    detectors["LSTM (next-action)"] = lstm_scores(
        train, eval_items, vocab, args.max_len, args.epochs, args.hidden, args.embed, args.seed
    )
    detectors["Isolation Forest"] = iso_scores(train, eval_items, args.seed)
    if not args.no_llm:
        detectors["LLM monitor"] = asyncio.run(llm_scores(eval_items))

    # Compute metrics
    rows = []
    for name, scores in detectors.items():
        pa = partial_auroc(labels, scores)
        f1, prec, rec, thr = best_f1(labels, scores)
        rows.append((name, pa, f1, prec, rec))

    # Markdown table
    header = "| Detector | pAUROC@FPR<0.2 | F1 | Precision | Recall |\n|---|---|---|---|---|"
    body = "\n".join(
        f"| {n} | {pa:.3f} | {f1:.3f} | {pr:.3f} | {rc:.3f} |" for (n, pa, f1, pr, rc) in rows
    )
    table = (
        f"# Anomaly Detector Comparison\n\n"
        f"Eval set: {len(val_normal)} held-out normal runs + {len(redteam)} red-team runs "
        f"(train: {len(train)} normal). Metric: partial AUROC at FPR<0.2 (Storf et al. 2026) + best-F1.\n\n"
        f"{header}\n{body}\n"
    )
    print("\n" + table)

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "comparison.md").write_text(table, encoding="utf-8")
    print(f"\nSaved {OUTPUTS / 'comparison.md'}")

    # MLflow
    mlflow.set_experiment("byteops-anomaly-eval")
    with mlflow.start_run():
        mlflow.log_params({"n_train": len(train), "n_val_normal": len(val_normal),
                           "n_redteam": len(redteam), "max_len": args.max_len, "epochs": args.epochs})
        for (n, pa, f1, pr, rc) in rows:
            key = n.split(" ")[0].lower()
            for metric, val in [("pauroc", pa), ("f1", f1), ("precision", pr), ("recall", rc)]:
                if not np.isnan(val):
                    mlflow.log_metric(f"{key}_{metric}", float(val))
        mlflow.log_artifact(str(OUTPUTS / "comparison.md"))
    print("Logged to MLflow experiment 'byteops-anomaly-eval' (view with: mlflow ui)")


if __name__ == "__main__":
    main()
