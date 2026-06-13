"""Experiment suite for the next-action LSTM anomaly detector.

Turns the project from "a model" into "a study". Two kinds of experiments:

LABEL-FREE (work on any data, including your current runs) — metric is mean
held-out validation NLL (lower = the model predicts NORMAL sequences better):
  1. Order ablation     — ordered vs shuffled token sequences. If ordered wins,
                          sequence modeling is justified (the core thesis).
  2. Sequence length    — max_len in {8, 12, 20}. Does more context help?
  3. Model capacity     — hidden size in {16, 48, 96}. Underfit vs overfit.
All run over multiple seeds and reported as mean +/- 95% CI.

LABEL-DEPENDENT (auto-run only if 'redteam' runs exist) — detection quality:
  4. Scoring rule       — max-NLL vs mean-NLL vs top-k miss (DeepLog's criterion),
                          scored by partial AUROC at FPR<0.2.

Usage:
  python scripts/run_experiments.py --data data/runs.jsonl --seeds 5 --epochs 20

Outputs: prints tables, writes outputs/experiments.md, logs to MLflow
('byteops-anomaly-experiments'). View with: mlflow ui --backend-store-uri sqlite:///mlflow.db
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.anomaly.tokenizer import PAD, build_vocab, encode_tokens  # noqa: E402

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"


# ── helpers ──────────────────────────────────────────────────────────────────

def mean_ci(values: list[float]) -> tuple[float, float]:
    """Mean and 95% (normal-approx) confidence half-width over seeds."""
    arr = np.asarray(values, dtype=float)
    m = float(arr.mean())
    if len(arr) < 2:
        return m, 0.0
    se = float(arr.std(ddof=1) / np.sqrt(len(arr)))
    return m, 1.96 * se


def partial_auroc(labels: np.ndarray, scores: np.ndarray, max_fpr: float = 0.2) -> float:
    order = np.argsort(-scores)
    labels = labels[order]
    P, N = labels.sum(), len(labels) - labels.sum()
    if P == 0 or N == 0:
        return float("nan")
    tpr = np.concatenate([[0.0], np.cumsum(labels) / P])
    fpr = np.concatenate([[0.0], np.cumsum(1 - labels) / N])
    area = 0.0
    for i in range(1, len(fpr)):
        if fpr[i - 1] >= max_fpr:
            break
        x0, x1 = fpr[i - 1], min(fpr[i], max_fpr)
        if x1 > x0:
            area += (x1 - x0) * (tpr[i] + tpr[i - 1]) / 2.0
    return float(area / max_fpr)


def _shuffle_tokens(seqs, rng):
    """Return copies of sequences with their token ORDER randomly permuted."""
    out = []
    for s in seqs:
        toks = list(s["tokens"])
        rng.shuffle(toks)
        out.append({**s, "tokens": toks})
    return out


# ── core: train an LSTM, return held-out val NLL + a per-run scorer ───────────

def train_lstm(train, val, vocab, max_len, hidden, embed, epochs, seed):
    import torch
    import torch.nn as nn

    torch.manual_seed(seed)
    vocab_size = len(vocab)

    def enc(items):
        return torch.tensor(
            [encode_tokens(s["tokens"], vocab, max_len) for s in items], dtype=torch.long
        )

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

    # mean per-token NLL on held-out validation (the label-free quality metric)
    model.eval()
    with torch.no_grad():
        xv = enc(val)
        logp = torch.log_softmax(model(xv), dim=-1)
        total, count = 0.0, 0
        for b in range(xv.shape[0]):
            for t in range(1, max_len):
                tok = xv[b, t].item()
                if tok == vocab[PAD]:
                    break
                total += -logp[b, t - 1, tok].item()
                count += 1
        val_nll = total / count if count else 0.0

    def session_scores(items, rule="max", k=1):
        out = []
        with torch.no_grad():
            x = enc(items)
            logp = torch.log_softmax(model(x), dim=-1)
            for b in range(x.shape[0]):
                vals = []
                for t in range(1, max_len):
                    tok = x[b, t].item()
                    if tok == vocab[PAD]:
                        break
                    if rule == "topk":
                        topk = torch.topk(logp[b, t - 1], k).indices.tolist()
                        vals.append(0.0 if tok in topk else 1.0)
                    else:
                        vals.append(-logp[b, t - 1, tok].item())
                if not vals:
                    out.append(0.0)
                elif rule == "mean":
                    out.append(float(np.mean(vals)))
                else:  # max or topk -> take the worst step
                    out.append(float(np.max(vals)))
        return np.array(out)

    return float(val_nll), session_scores


# ── main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    import mlflow

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/runs.jsonl")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--epochs", type=int, default=20)
    args = parser.parse_args()

    seqs = [json.loads(l) for l in Path(args.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    normal = [s for s in seqs if s["label"] in ("normal", "unlabeled")]
    redteam = [s for s in seqs if s["label"] == "redteam"]
    if len(normal) < 6:
        print(f"WARNING: only {len(normal)} normal runs — results will be noisy but valid.")

    def split(items, seed):
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(items))
        cut = max(1, int(0.8 * len(items)))
        return [items[i] for i in idx[:cut]], ([items[i] for i in idx[cut:]] or [items[idx[0]]])

    lines = ["# Anomaly Detector — Experiment Suite\n",
             f"Data: {len(normal)} normal runs, {len(redteam)} red-team runs. "
             f"Seeds: {args.seeds}, epochs: {args.epochs}.\n",
             "Label-free metric = mean held-out validation NLL (lower = better next-action prediction).\n"]

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("byteops-anomaly-experiments")
    mlflow.start_run()  # one run for the whole suite; metrics + report logged into it

    # ── Experiment 1: order ablation (ordered vs shuffled) ──
    print("\n[1/3] Order ablation (ordered vs shuffled)...")
    ordered_nlls, shuffled_nlls = [], []
    for seed in range(args.seeds):
        tr, va = split(normal, seed)
        vocab = build_vocab([s["tokens"] for s in tr])
        nll_o, _ = train_lstm(tr, va, vocab, 12, 48, 32, args.epochs, seed)
        rng = np.random.default_rng(1000 + seed)
        tr_s, va_s = _shuffle_tokens(tr, rng), _shuffle_tokens(va, rng)
        vocab_s = build_vocab([s["tokens"] for s in tr_s])
        nll_s, _ = train_lstm(tr_s, va_s, vocab_s, 12, 48, 32, args.epochs, seed)
        ordered_nlls.append(nll_o); shuffled_nlls.append(nll_s)
    mo, co = mean_ci(ordered_nlls); ms, cs = mean_ci(shuffled_nlls)
    verdict = "order HELPS (sequence modeling justified)" if mo < ms else "order shows little effect at this data size"
    lines += ["\n## 1. Order ablation\n",
              "| Sequence | Val NLL (mean +/- 95% CI) |\n|---|---|",
              f"| Ordered  | {mo:.4f} +/- {co:.4f} |",
              f"| Shuffled | {ms:.4f} +/- {cs:.4f} |",
              f"\n**Result:** {verdict}.\n"]
    mlflow.log_metric("order_ordered_val_nll", mo)
    mlflow.log_metric("order_shuffled_val_nll", ms)

    # ── Experiment 2: sequence-length sensitivity ──
    print("[2/3] Sequence-length sensitivity (8/12/20)...")
    lines += ["\n## 2. Sequence-length sensitivity\n", "| max_len | Val NLL (mean +/- 95% CI) |\n|---|---|"]
    for ml in (8, 12, 20):
        nlls = []
        for seed in range(args.seeds):
            tr, va = split(normal, seed)
            vocab = build_vocab([s["tokens"] for s in tr])
            nll, _ = train_lstm(tr, va, vocab, ml, 48, 32, args.epochs, seed)
            nlls.append(nll)
        m, c = mean_ci(nlls)
        lines.append(f"| {ml} | {m:.4f} +/- {c:.4f} |")
        mlflow.log_metric(f"seqlen_{ml}_val_nll", m)

    # ── Experiment 3: model capacity ──
    print("[3/3] Model capacity (hidden 16/48/96)...")
    lines += ["\n## 3. Model capacity (hidden size)\n", "| hidden | Val NLL (mean +/- 95% CI) |\n|---|---|"]
    for hid in (16, 48, 96):
        nlls = []
        for seed in range(args.seeds):
            tr, va = split(normal, seed)
            vocab = build_vocab([s["tokens"] for s in tr])
            nll, _ = train_lstm(tr, va, vocab, 12, hid, 32, args.epochs, seed)
            nlls.append(nll)
        m, c = mean_ci(nlls)
        lines.append(f"| {hid} | {m:.4f} +/- {c:.4f} |")
        mlflow.log_metric(f"hidden_{hid}_val_nll", m)

    # ── Experiment 4: scoring-rule comparison (needs red-team labels) ──
    lines += ["\n## 4. Scoring-rule comparison (detection)\n"]
    if not redteam:
        lines.append("_Skipped: no red-team runs labeled yet. Label some with "
                      "`scripts/label_redteam.py`, re-export, and re-run to populate this._\n")
        print("[4] Scoring-rule comparison SKIPPED (no red-team runs).")
    else:
        lines.append("| Scoring rule | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|")
        for rule, k in [("max", 1), ("mean", 1), ("topk", 1), ("topk", 2)]:
            pas = []
            for seed in range(args.seeds):
                tr, va = split(normal, seed)
                vocab = build_vocab([s["tokens"] for s in tr])
                _, scorer = train_lstm(tr, va, vocab, 12, 48, 32, args.epochs, seed)
                eval_items = va + redteam
                labels = np.array([0] * len(va) + [1] * len(redteam))
                pa = partial_auroc(labels, scorer(eval_items, rule=rule, k=k))
                if not np.isnan(pa):
                    pas.append(pa)
            if pas:
                m, c = mean_ci(pas)
                name = f"{rule}" + (f"(k={k})" if rule == "topk" else "")
                lines.append(f"| {name} | {m:.3f} +/- {c:.3f} |")
                mlflow.log_metric(f"score_{rule}{k}_pauroc", m)

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    report = "\n".join(lines) + "\n"
    (OUTPUTS / "experiments.md").write_text(report, encoding="utf-8")
    mlflow.log_artifact(str(OUTPUTS / "experiments.md"))
    mlflow.end_run()
    print("\n" + report)
    print(f"Saved {OUTPUTS / 'experiments.md'}  (MLflow experiment: byteops-anomaly-experiments)")


if __name__ == "__main__":
    main()
