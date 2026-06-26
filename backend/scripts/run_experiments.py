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


# ── supervised ablation trainer (feature-based BiLSTM/Transformer) ─────────────

def _supervised_scores_ablation(model_name, train, test, *, shuffle=False, zero_num=False,
                                zero_intent=False, attention=True, max_len=20, epochs=40, seed=42):
    """Train a feature model with optional ablation flags; return test anomaly scores.

    Mirrors evaluate_detectors.supervised_scores, adding:
      shuffle=True     -> permute each run's steps before encoding (kills order signal)
      zero_num=True    -> zero the numeric feature block (kills risk-level/external/etc.)
      zero_intent=True -> zero ONLY the intent/context columns (kills intent-vs-tool signal)
      attention=False  -> mean-pool LSTM outputs instead of attending (BiLSTM only)
    """
    import random
    import torch
    import torch.nn as nn
    from app.anomaly.features import build_feature_vocabs, encode_run, CATEGORICAL_FIELDS, NUMERIC_FEATURES, INTENT_FEATURES
    _intent_cols = [NUMERIC_FEATURES.index(f) for f in INTENT_FEATURES]
    from app.anomaly.models import BiLSTMAttention, TransformerEncoderClassifier
    torch.manual_seed(seed)

    def prep(items):
        out = []
        for r in items:
            steps = list(r["steps"])
            if shuffle:
                random.Random(seed).shuffle(steps)
            out.append({**r, "steps": steps})
        return out

    train, test = prep(train), prep(test)
    vocabs = build_feature_vocabs([r["steps"] for r in train])
    vsz = {f: len(vocabs[f]) for f in CATEGORICAL_FIELDS}

    def batch(items):
        enc = [encode_run(r["steps"], vocabs, max_len, r.get("intent", "general")) for r in items]
        cat = {f: torch.tensor([e["cat"][f] for e in enc]) for f in CATEGORICAL_FIELDS}
        num = torch.tensor([e["num"] for e in enc], dtype=torch.float32)
        if zero_num:
            num = torch.zeros_like(num)
        elif zero_intent:
            num[:, :, _intent_cols] = 0.0
        mask = torch.tensor([e["mask"] for e in enc], dtype=torch.float32)
        y = torch.tensor([1.0 if r["label"] == "redteam" else 0.0 for r in items])
        return cat, num, mask, y

    if model_name == "transformer":
        model = TransformerEncoderClassifier(vsz, len(NUMERIC_FEATURES))
    else:
        model = BiLSTMAttention(vsz, len(NUMERIC_FEATURES))
        if not attention:
            import types

            def mp_forward(self, cat, num, mask):
                x = self.embed(cat, num)
                out, _ = self.lstm(x)
                m = mask.unsqueeze(-1)
                ctx = (out * m).sum(1) / m.sum(1).clamp(min=1)
                return self.head(self.drop(ctx)).squeeze(-1), mask

            model.forward = types.MethodType(mp_forward, model)

    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    cat_tr, num_tr, mask_tr, y_tr = batch(train)
    n_pos = max(1.0, float((y_tr == 1).sum())); n_neg = max(1.0, float((y_tr == 0).sum()))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(n_neg / n_pos))
    model.train()
    for _ in range(epochs):
        perm = torch.randperm(y_tr.shape[0])
        for i in range(0, y_tr.shape[0], 32):
            bi = perm[i:i + 32]
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


def _iso_scores_tokens(train, test, seed):
    """Classical Isolation Forest baseline on simple token-derived features."""
    from sklearn.ensemble import IsolationForest
    from app.anomaly.tokenizer import run_to_tokens

    def feats(items):
        rows = []
        for s in items:
            toks = s.get("tokens") or run_to_tokens(s.get("steps", []))
            n = len(toks) or 1
            ext = sum(1 for t in toks if "external_send" in t or "destructive" in t)
            rows.append([n, ext / n, len(set(toks)) / n])
        return np.array(rows) if items else np.zeros((0, 3))

    iso = IsolationForest(n_estimators=200, contamination=0.2, random_state=seed)
    iso.fit(feats(train))
    return -iso.decision_function(feats(test))


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

    from app.anomaly.tokenizer import run_to_tokens  # noqa: E402

    seqs = [json.loads(l) for l in Path(args.data).read_text(encoding="utf-8").splitlines() if l.strip()]
    # Label-free experiments operate on flat token sequences; derive them from rich
    # `steps` when a dataset (e.g. generate_dataset.py output) ships without `tokens`.
    for s in seqs:
        if "tokens" not in s:
            s["tokens"] = run_to_tokens(s.get("steps", []))
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
    print("\n[1/5] Order ablation (ordered vs shuffled)...")
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
    print("[2/5] Sequence-length sensitivity (8/12/20)...")
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
    print("[3/5] Model capacity (hidden 16/48/96)...")
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

    # ── Supervised ablations (feature-based models; needs red-team labels) ──
    lines += ["\n## Supervised ablations\n"]
    if not redteam or len(redteam) < 2 or len(normal) < 2:
        lines.append("_Skipped: need >=2 normal and >=2 red-team runs for a supervised "
                      "70/30-by-class split. Generate/label more data and re-run._\n")
        print("[5] Supervised ablations SKIPPED (insufficient labeled data).")
    else:
        print("[5/5] Supervised ablations (order/risk-features/attention/arch/classical)...")
        lines += ["Metric = partial AUROC at FPR<0.2 on a held-out 70/30-by-class test "
                  "split (both classes in train), mean +/- 95% CI over seeds.\n"]

        def class_split(seed):
            """70/30 split per class; both classes present in train and test."""
            rng = np.random.default_rng(seed)
            ni = rng.permutation(len(normal)); ri = rng.permutation(len(redteam))
            ncut = max(1, int(0.7 * len(normal))); rcut = max(1, int(0.7 * len(redteam)))
            n_tr = [normal[i] for i in ni[:ncut]]
            n_te = [normal[i] for i in ni[ncut:]] or [normal[ni[0]]]
            r_tr = [redteam[i] for i in ri[:rcut]]
            r_te = [redteam[i] for i in ri[rcut:]] or [redteam[ri[0]]]
            train = n_tr + r_tr
            test = n_te + r_te
            labels = np.array([0] * len(n_te) + [1] * len(r_te))
            return train, test, labels

        def run_variant(label, key, **kwargs):
            """Train the variant over all seeds, append a table row, log to MLflow."""
            pas = []
            for seed in range(args.seeds):
                train, test, labels = class_split(seed)
                if kwargs.get("_iso"):
                    scores = _iso_scores_tokens(train, test, seed)
                else:
                    scores = _supervised_scores_ablation(
                        kwargs["model_name"], train, test,
                        shuffle=kwargs.get("shuffle", False),
                        zero_num=kwargs.get("zero_num", False),
                        zero_intent=kwargs.get("zero_intent", False),
                        attention=kwargs.get("attention", True),
                        epochs=args.epochs, seed=seed,
                    )
                pa = partial_auroc(labels, np.asarray(scores, dtype=float))
                if not np.isnan(pa):
                    pas.append(pa)
            if not pas:
                lines.append(f"| {label} | n/a |")
                return
            m, c = mean_ci(pas)
            lines.append(f"| {label} | {m:.3f} +/- {c:.3f} |")
            mlflow.log_metric(f"ablation_{key}_pauroc", m)
            return m

        # 1) Sequence order — BiLSTM+Attention, ordered vs shuffled steps.
        lines += ["\n### Sequence order (BiLSTM+Attention)\n",
                  "| Variant | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|"]
        run_variant("Ordered steps", "order_ordered", model_name="bilstm_attn", shuffle=False)
        run_variant("Shuffled steps", "order_shuffled", model_name="bilstm_attn", shuffle=True)

        # 2) Risk features — full numeric block vs zeroed numeric block.
        lines += ["\n### Risk features (BiLSTM+Attention)\n",
                  "| Variant | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|"]
        run_variant("Full features", "risk_full", model_name="bilstm_attn", zero_num=False)
        run_variant("Risk features zeroed", "risk_zeroed", model_name="bilstm_attn", zero_num=True)

        # 2b) Intent/context features — full vs intent columns zeroed. This is the key
        #     ablation: without intent context the model can't tell an authorized risky
        #     action (hard negative) from an unauthorized one (subtle positive).
        lines += ["\n### Intent / context features (BiLSTM+Attention)\n",
                  "| Variant | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|"]
        run_variant("With intent features", "intent_on", model_name="bilstm_attn", zero_intent=False)
        run_variant("Intent features zeroed", "intent_off", model_name="bilstm_attn", zero_intent=True)

        # 3) Attention — attention pooling vs masked mean-pool (BiLSTM).
        lines += ["\n### Attention vs mean-pool (BiLSTM)\n",
                  "| Variant | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|"]
        run_variant("BiLSTM + Attention", "attn_on", model_name="bilstm_attn", attention=True)
        run_variant("BiLSTM mean-pool", "attn_off", model_name="bilstm_attn", attention=False)

        # 4) Architecture — BiLSTM+Attention vs Transformer.
        lines += ["\n### Architecture (BiLSTM+Attn vs Transformer)\n",
                  "| Variant | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|"]
        run_variant("BiLSTM + Attention", "arch_bilstm", model_name="bilstm_attn")
        run_variant("Transformer", "arch_transformer", model_name="transformer")

        # 5) Classical vs learned — Isolation Forest vs BiLSTM+Attention.
        lines += ["\n### Classical vs learned (Isolation Forest vs BiLSTM+Attn)\n",
                  "| Variant | pAUROC@FPR<0.2 (mean +/- 95% CI) |\n|---|---|"]
        run_variant("Isolation Forest", "classical_iso", _iso=True)
        run_variant("BiLSTM + Attention", "classical_bilstm", model_name="bilstm_attn")

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    report = "\n".join(lines) + "\n"
    (OUTPUTS / "experiments.md").write_text(report, encoding="utf-8")
    mlflow.log_artifact(str(OUTPUTS / "experiments.md"))
    mlflow.end_run()
    print("\n" + report)
    print(f"Saved {OUTPUTS / 'experiments.md'}  (MLflow experiment: byteops-anomaly-experiments)")


if __name__ == "__main__":
    main()
