"""Train BiLSTM+Attention and emit report-ready artifacts for the DL course:
  outputs/confusion_matrix.png, outputs/roc_curve.png, outputs/attention_example.png,
  outputs/report_summary.md
Offline. Usage: python scripts/make_report.py --data data/gen.jsonl --epochs 50
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.anomaly.features import build_feature_vocabs, encode_run, CATEGORICAL_FIELDS, NUMERIC_FEATURES  # noqa: E402
from app.anomaly import metrics as M  # noqa: E402

OUTPUTS = Path(__file__).resolve().parent.parent / "outputs"


def _load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    import torch, torch.nn as nn
    from app.anomaly.models import BiLSTMAttention

    p = argparse.ArgumentParser()
    p.add_argument("--data", default="data/gen.jsonl")
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--max-len", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    a = p.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)

    runs = _load(a.data)
    rng = np.random.default_rng(a.seed)
    # 70/30 split by class
    norm = [r for r in runs if r["label"] != "redteam"]
    anom = [r for r in runs if r["label"] == "redteam"]
    def split(items):
        idx = rng.permutation(len(items)); c = int(0.7 * len(items))
        return [items[i] for i in idx[:c]], [items[i] for i in idx[c:]]
    n_tr, n_te = split(norm); a_tr, a_te = split(anom)
    train, test = n_tr + a_tr, n_te + a_te

    vocabs = build_feature_vocabs([r["steps"] for r in train])
    vsz = {f: len(vocabs[f]) for f in CATEGORICAL_FIELDS}

    def batch(items):
        enc = [encode_run(r["steps"], vocabs, a.max_len) for r in items]
        cat = {f: torch.tensor([e["cat"][f] for e in enc]) for f in CATEGORICAL_FIELDS}
        num = torch.tensor([e["num"] for e in enc], dtype=torch.float32)
        mask = torch.tensor([e["mask"] for e in enc], dtype=torch.float32)
        y = torch.tensor([1.0 if r["label"] == "redteam" else 0.0 for r in items])
        return cat, num, mask, y

    model = BiLSTMAttention(vsz, len(NUMERIC_FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    cat_tr, num_tr, mask_tr, y_tr = batch(train)
    n_pos = max(1.0, float((y_tr == 1).sum())); n_neg = max(1.0, float((y_tr == 0).sum()))
    loss_fn = nn.BCEWithLogitsLoss(pos_weight=torch.tensor(n_neg / n_pos))
    model.train()
    for _ in range(a.epochs):
        perm = torch.randperm(y_tr.shape[0])
        for i in range(0, y_tr.shape[0], 32):
            bi = perm[i:i + 32]
            cb = {f: cat_tr[f][bi] for f in CATEGORICAL_FIELDS}
            opt.zero_grad()
            logit, _ = model(cb, num_tr[bi], mask_tr[bi]); loss_fn(logit, y_tr[bi]).backward(); opt.step()

    model.eval()
    cat_te, num_te, mask_te, y_te = batch(test)
    with torch.no_grad():
        logit, _ = model(cat_te, num_te, mask_te)
        scores = torch.sigmoid(logit).numpy()
    labels = y_te.numpy()
    cm = M.classification_metrics(labels, scores, 0.5)
    pa, au = M.partial_auroc(labels, scores), M.auroc(labels, scores)

    OUTPUTS.mkdir(parents=True, exist_ok=True)

    # 1) confusion matrix
    tp, fp, fn, tn = M.confusion(labels, (scores >= 0.5).astype(int))
    mat = np.array([[tn, fp], [fn, tp]])
    fig, ax = plt.subplots(figsize=(4, 3.5))
    ax.imshow(mat, cmap="Blues")
    ax.set_xticks([0, 1], ["Pred normal", "Pred anomalous"])
    ax.set_yticks([0, 1], ["True normal", "True anomalous"])
    for (i, j), v in np.ndenumerate(mat):
        ax.text(j, i, str(v), ha="center", va="center", fontsize=14)
    ax.set_title("BiLSTM+Attention — Confusion Matrix")
    fig.tight_layout(); fig.savefig(OUTPUTS / "confusion_matrix.png", dpi=120); plt.close(fig)

    # 2) ROC curve
    fpr, tpr = M.roc_points(labels, scores)
    fig, ax = plt.subplots(figsize=(4.5, 4))
    ax.plot(fpr, tpr, label=f"BiLSTM+Attn (AUROC={au:.3f})")
    ax.plot([0, 1], [0, 1], "--", color="gray", label="random")
    ax.axvspan(0, 0.2, color="orange", alpha=0.1, label="pAUROC region (FPR<0.2)")
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.set_title("ROC Curve"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(OUTPUTS / "roc_curve.png", dpi=120); plt.close(fig)

    # 3) attention example for one flagged anomalous run
    flagged = [r for r in test if r["label"] == "redteam"] or test
    ex = flagged[0]
    enc = encode_run(ex["steps"], vocabs, a.max_len)
    fe = {f: torch.tensor([enc["cat"][f]]) for f in CATEGORICAL_FIELDS}
    with torch.no_grad():
        _, attn = model(fe, torch.tensor([enc["num"]], dtype=torch.float32),
                        torch.tensor([enc["mask"]], dtype=torch.float32))
    attn = attn[0].numpy()
    n = min(len(ex["steps"]), a.max_len)
    names = [ex["steps"][i].get("name", f"step{i}") for i in range(n)]
    fig, ax = plt.subplots(figsize=(max(6, n), 2.6))
    ax.bar(range(n), attn[:n], color="#EF4444")
    ax.set_xticks(range(n)); ax.set_xticklabels(names, rotation=35, ha="right", fontsize=8)
    ax.set_ylabel("attention"); ax.set_title("Attention over steps — flagged run (brighter = drove the flag)")
    fig.tight_layout(); fig.savefig(OUTPUTS / "attention_example.png", dpi=120); plt.close(fig)

    # 4) markdown summary
    (OUTPUTS / "report_summary.md").write_text(
        "# BiLSTM+Attention — Report Summary\n\n"
        f"Test set: {len(test)} runs ({len(a_te)} anomalous). Threshold 0.5.\n\n"
        f"| Metric | Value |\n|---|---|\n"
        f"| Accuracy | {cm['accuracy']:.3f} |\n| Precision | {cm['precision']:.3f} |\n"
        f"| Recall | {cm['recall']:.3f} |\n| F1 | {cm['f1']:.3f} |\n"
        f"| AUROC | {au:.3f} |\n| pAUROC@FPR<0.2 | {pa:.3f} |\n\n"
        "Artifacts: confusion_matrix.png, roc_curve.png, attention_example.png.\n",
        encoding="utf-8")
    print("Wrote outputs/{confusion_matrix.png, roc_curve.png, attention_example.png, report_summary.md}")
    print(json.dumps({**cm, "pauroc": pa, "auroc": au}, indent=2))


if __name__ == "__main__":
    main()
