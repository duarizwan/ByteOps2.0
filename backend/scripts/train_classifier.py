"""Train a supervised anomaly classifier (BiLSTM+Attention / Transformer) on rich
feature sequences. Offline. Logs to MLflow; exports ONNX + meta.

Usage:
  python scripts/train_classifier.py --data data/gen.jsonl --model bilstm_attn --epochs 40
  python scripts/train_classifier.py --data data/gen.jsonl --model transformer --holdout-type privilege
"""
from __future__ import annotations

import argparse, json, os, sys
from pathlib import Path
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.anomaly.features import build_feature_vocabs, encode_run, CATEGORICAL_FIELDS, NUMERIC_FEATURES  # noqa: E402
from app.anomaly import metrics as M  # noqa: E402

ARTIFACTS = Path(__file__).resolve().parent.parent / "app" / "anomaly" / "artifacts"


def _load(path):
    return [json.loads(l) for l in Path(path).read_text(encoding="utf-8").splitlines() if l.strip()]


def main():
    import torch, torch.nn as nn, mlflow
    from app.anomaly.models import BiLSTMAttention, TransformerEncoderClassifier

    p = argparse.ArgumentParser()
    p.add_argument("--data", required=True)
    p.add_argument("--model", choices=["bilstm_attn", "transformer"], default="bilstm_attn")
    p.add_argument("--epochs", type=int, default=40)
    p.add_argument("--max-len", type=int, default=20)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--holdout-type", default="")
    a = p.parse_args()
    torch.manual_seed(a.seed); np.random.seed(a.seed)

    runs = _load(a.data)
    rng = np.random.default_rng(a.seed)
    def is_holdout(r): return a.holdout_type and r.get("anomaly_type") == a.holdout_type
    pool = [r for r in runs if not is_holdout(r)]
    held = [r for r in runs if is_holdout(r)]
    idx = rng.permutation(len(pool))
    n = len(pool); tr_end = int(.7*n); va_end = int(.85*n)
    train = [pool[i] for i in idx[:tr_end]]
    val   = [pool[i] for i in idx[tr_end:va_end]]
    test  = [pool[i] for i in idx[va_end:]] + held

    vocabs = build_feature_vocabs([r["steps"] for r in train])
    vocab_sizes = {f: len(vocabs[f]) for f in CATEGORICAL_FIELDS}

    def batch(items):
        enc = [encode_run(r["steps"], vocabs, a.max_len) for r in items]
        cat = {f: torch.tensor([e["cat"][f] for e in enc]) for f in CATEGORICAL_FIELDS}
        num = torch.tensor([e["num"] for e in enc], dtype=torch.float32)
        mask = torch.tensor([e["mask"] for e in enc], dtype=torch.float32)
        y = torch.tensor([1.0 if r["label"] == "redteam" else 0.0 for r in items])
        return cat, num, mask, y

    Model = BiLSTMAttention if a.model == "bilstm_attn" else TransformerEncoderClassifier
    model = Model(vocab_sizes, len(NUMERIC_FEATURES))
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCEWithLogitsLoss()
    cat_tr, num_tr, mask_tr, y_tr = batch(train)
    cat_va, num_va, mask_va, y_va = batch(val)

    mlflow.set_tracking_uri("sqlite:///mlflow.db"); mlflow.set_experiment("byteops-anomaly-clf")
    best_val, best_state, patience, bad = 1e9, None, 6, 0
    with mlflow.start_run():
        mlflow.log_params({"model": a.model, "epochs": a.epochs, "max_len": a.max_len,
                           "holdout_type": a.holdout_type or "none", "n_train": len(train),
                           "tokenizer": "v2"})
        for ep in range(a.epochs):
            model.train(); opt.zero_grad()
            logit, _ = model(cat_tr, num_tr, mask_tr)
            loss = loss_fn(logit, y_tr); loss.backward(); opt.step()
            model.eval()
            with torch.no_grad():
                vlogit, _ = model(cat_va, num_va, mask_va)
                vloss = loss_fn(vlogit, y_va).item()
            if vloss < best_val:
                best_val = vloss; best_state = {k: v.clone() for k, v in model.state_dict().items()}; bad = 0
            else:
                bad += 1
                if bad >= patience: break
        if best_state: model.load_state_dict(best_state)

        model.eval()
        cat_te, num_te, mask_te, y_te = batch(test)
        with torch.no_grad():
            tlogit, _ = model(cat_te, num_te, mask_te)
            scores = torch.sigmoid(tlogit).numpy()
        labels = y_te.numpy(); thr = 0.5
        cm = M.classification_metrics(labels, scores, thr)
        result = {**cm, "pauroc": M.partial_auroc(labels, scores), "auroc": M.auroc(labels, scores)}
        mlflow.log_metrics({k: float(v) for k, v in result.items()})

        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        dummy_cat = tuple(cat_te[f][:1] for f in CATEGORICAL_FIELDS)
        emit_attn = (a.model == "bilstm_attn")

        class Wrap(nn.Module):
            def __init__(s, mdl, attn): super().__init__(); s.m = mdl; s.attn = attn
            def forward(s, st, tn, ac, num, mask):
                logit, attn = s.m({"step_type": st, "tool_name": tn, "action_category": ac}, num, mask)
                return (logit, attn) if s.attn else logit

        onnx_path = ARTIFACTS / f"clf_{a.model}.onnx"
        out_names = ["logit", "attn"] if emit_attn else ["logit"]
        torch.onnx.export(Wrap(model, emit_attn),
                          (*dummy_cat, num_te[:1], mask_te[:1]),
                          str(onnx_path),
                          input_names=["step_type", "tool_name", "action_category", "num", "mask"],
                          output_names=out_names, opset_version=14, dynamo=False)
        (ARTIFACTS / f"clf_{a.model}_meta.json").write_text(json.dumps({
            "model": a.model, "tokenizer": "v2", "max_len": a.max_len, "threshold": thr,
            "vocabs": vocabs, "numeric_features": NUMERIC_FEATURES, "metrics": result,
            "emits_attention": emit_attn,
        }, indent=2), encoding="utf-8")
        print(json.dumps(result, indent=2)); print("Saved", onnx_path)


if __name__ == "__main__":
    main()
