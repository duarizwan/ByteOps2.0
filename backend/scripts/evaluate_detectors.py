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
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.anomaly.tokenizer import PAD, build_vocab, encode_tokens, run_to_tokens  # noqa: E402
from app.anomaly import metrics as M  # noqa: E402

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

    def _toks(s):
        return s.get("tokens") or run_to_tokens(s.get("steps", []))

    def enc(items):
        return torch.tensor([encode_tokens(_toks(s), vocab, max_len) for s in items], dtype=torch.long)

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
            toks = s.get("tokens") or run_to_tokens(s.get("steps", [])); n = len(toks) or 1
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
        for tok in (s.get("tokens") or run_to_tokens(s.get("steps", []))):
            parts = tok.split("|")
            step_type = parts[0] if parts else "step"
            name = parts[1] if len(parts) > 1 else tok
            status = parts[2] if len(parts) > 2 else "completed"
            steps.append({"step_type": step_type, "name": name, "status": status})
        res = await score_run_llm(steps)
        out.append(float(res["score"]) if res else 5.0)
    return np.array(out)


def supervised_scores(model_name, train, test, max_len=20, epochs=40, seed=42):
    """Train BiLSTM+Attention or Transformer on `train`, return anomaly scores for `test`."""
    import torch, torch.nn as nn
    from app.anomaly.features import build_feature_vocabs, encode_run, CATEGORICAL_FIELDS, NUMERIC_FEATURES
    from app.anomaly.models import BiLSTMAttention, TransformerEncoderClassifier
    torch.manual_seed(seed)
    vocabs = build_feature_vocabs([r["steps"] for r in train])
    vsz = {f: len(vocabs[f]) for f in CATEGORICAL_FIELDS}

    def batch(items):
        enc = [encode_run(r["steps"], vocabs, max_len) for r in items]
        cat = {f: torch.tensor([e["cat"][f] for e in enc]) for f in CATEGORICAL_FIELDS}
        num = torch.tensor([e["num"] for e in enc], dtype=torch.float32)
        mask = torch.tensor([e["mask"] for e in enc], dtype=torch.float32)
        y = torch.tensor([1.0 if r["label"] == "redteam" else 0.0 for r in items])
        return cat, num, mask, y

    Model = BiLSTMAttention if model_name == "bilstm_attn" else TransformerEncoderClassifier
    model = Model(vsz, len(NUMERIC_FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    cat_tr, num_tr, mask_tr, y_tr = batch(train)
    n_pos = max(1.0, float((y_tr == 1).sum())); n_neg = max(1.0, float((y_tr == 0).sum()))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(n_neg / n_pos))
    model.train()
    for _ in range(epochs):
        perm = torch.randperm(y_tr.shape[0])
        for i in range(0, y_tr.shape[0], 32):
            bi = perm[i:i+32]
            cb = {f: cat_tr[f][bi] for f in CATEGORICAL_FIELDS}
            opt.zero_grad()
            logit, _ = model(cb, num_tr[bi], mask_tr[bi])
            loss_fn(logit, y_tr[bi]).backward()
            opt.step()
    model.eval()
    cat_te, num_te, mask_te, _ = batch(test)
    with torch.no_grad():
        logit, _ = model(cat_te, num_te, mask_te)
        return torch.sigmoid(logit).numpy()


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
    # Split BOTH classes 70/30 so the test set is identical for every detector and
    # the supervised models still see redteam examples during training.
    idx = rng.permutation(len(normal))
    cut = max(1, int(0.7 * len(normal)))
    train = [normal[i] for i in idx[:cut]]               # normal-train (unsupervised fit)
    val_normal = [normal[i] for i in idx[cut:]] or [normal[idx[0]]]

    ridx = rng.permutation(len(redteam))
    rcut = max(1, int(0.7 * len(redteam))) if len(redteam) > 1 else 0
    redteam_train = [redteam[i] for i in ridx[:rcut]]    # redteam-train (supervised only)
    redteam_test = [redteam[i] for i in ridx[rcut:]] or list(redteam)

    # Eval set: held-out normal (label 0) + held-out redteam (label 1) — same for all.
    eval_items = val_normal + redteam_test
    labels = np.array([0] * len(val_normal) + [1] * len(redteam_test))

    # Supervised models need BOTH classes in training: normal-train + redteam-train.
    sup_train = train + redteam_train

    vocab = build_vocab([s.get("tokens") or run_to_tokens(s.get("steps", [])) for s in train])

    detectors: dict[str, np.ndarray] = {}
    detectors["LSTM (next-action)"] = lstm_scores(
        train, eval_items, vocab, args.max_len, args.epochs, args.hidden, args.embed, args.seed
    )
    detectors["Isolation Forest"] = iso_scores(train, eval_items, args.seed)
    detectors["BiLSTM+Attention"] = supervised_scores("bilstm_attn", sup_train, eval_items, seed=args.seed)
    detectors["Transformer"] = supervised_scores("transformer", sup_train, eval_items, seed=args.seed)
    if not args.no_llm:
        detectors["LLM monitor"] = asyncio.run(llm_scores(eval_items))

    # Compute full metric set for every detector (accuracy/precision/recall/F1/AUROC/pAUROC).
    rows = []
    for name, scores in detectors.items():
        scores = np.asarray(scores, dtype=float)
        pa = M.partial_auroc(labels, scores)
        au = M.auroc(labels, scores)
        # Use the F1-maximizing threshold for the point metrics, consistent across detectors.
        _f1, _pr, _rc, thr = best_f1(labels, scores)
        cm = M.classification_metrics(labels, scores, thr)
        rows.append((name, cm["accuracy"], cm["precision"], cm["recall"], cm["f1"], au, pa))

    # Markdown table
    header = ("| Detector | Accuracy | Precision | Recall | F1 | AUROC | pAUROC@FPR<0.2 |\n"
              "|---|---|---|---|---|---|---|")
    body = "\n".join(
        f"| {n} | {acc:.3f} | {pr:.3f} | {rc:.3f} | {f1:.3f} | {au:.3f} | {pa:.3f} |"
        for (n, acc, pr, rc, f1, au, pa) in rows
    )
    table = (
        f"# Anomaly Detector Comparison\n\n"
        f"Eval set: {len(val_normal)} held-out normal runs + {len(redteam_test)} red-team runs "
        f"(unsupervised train: {len(train)} normal; supervised train: {len(train)} normal + "
        f"{len(redteam_train)} red-team). "
        f"Metrics: accuracy/precision/recall/F1 at the F1-optimal threshold, AUROC, and "
        f"partial AUROC at FPR<0.2 (Storf et al. 2026).\n\n"
        f"{header}\n{body}\n"
    )
    print("\n" + table)

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    (OUTPUTS / "comparison.md").write_text(table, encoding="utf-8")
    print(f"\nSaved {OUTPUTS / 'comparison.md'}")

    # MLflow
    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("byteops-anomaly-eval")
    with mlflow.start_run():
        mlflow.log_params({"n_train": len(train), "n_val_normal": len(val_normal),
                           "n_redteam_train": len(redteam_train), "n_redteam_test": len(redteam_test),
                           "max_len": args.max_len, "epochs": args.epochs})
        for (n, acc, pr, rc, f1, au, pa) in rows:
            key = n.split(" ")[0].lower().replace("+", "_")
            for metric, val in [("accuracy", acc), ("precision", pr), ("recall", rc),
                                ("f1", f1), ("auroc", au), ("pauroc", pa)]:
                if not np.isnan(val):
                    mlflow.log_metric(f"{key}_{metric}", float(val))
        mlflow.log_artifact(str(OUTPUTS / "comparison.md"))
    print("Logged to MLflow experiment 'byteops-anomaly-eval' (view with: mlflow ui)")


if __name__ == "__main__":
    main()
