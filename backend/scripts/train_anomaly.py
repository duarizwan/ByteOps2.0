"""Train a next-action LSTM (self-supervised) + Isolation Forest baseline on
REAL exported run sequences, then export ONNX + vocab + meta + metrics.

Usage:
  python scripts/train_anomaly.py --data data/runs.jsonl --epochs 30 --max-len 12

Trains ONLY on label=='normal'/'unlabeled' sequences; 'redteam' held out for eval.
Logs to MLflow (experiment 'byteops-anomaly')."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from app.anomaly.tokenizer import PAD, build_vocab, encode_tokens

ARTIFACTS = Path(__file__).resolve().parent.parent / "app" / "anomaly" / "artifacts"


def load_sequences(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    import mlflow
    import torch
    import torch.nn as nn
    from sklearn.ensemble import IsolationForest

    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/runs.jsonl")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--max-len", type=int, default=12)
    parser.add_argument("--hidden", type=int, default=48)
    parser.add_argument("--embed", type=int, default=32)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)

    mlflow.set_experiment("byteops-anomaly")

    seqs = load_sequences(Path(args.data))
    normal = [s for s in seqs if s["label"] in ("normal", "unlabeled")]
    redteam = [s for s in seqs if s["label"] == "redteam"]
    if len(normal) < 20:
        print(f"WARNING: only {len(normal)} normal runs - metrics will be weak.")

    mlflow.start_run()
    mlflow.log_params({
        "epochs": args.epochs, "max_len": args.max_len, "hidden": args.hidden,
        "embed": args.embed, "n_normal": len(normal), "n_redteam": len(redteam),
    })

    rng = np.random.default_rng(args.seed)
    idx = rng.permutation(len(normal))
    cut = max(1, int(0.8 * len(normal)))
    train = [normal[i] for i in idx[:cut]]
    val = [normal[i] for i in idx[cut:]] or train[:1]

    vocab = build_vocab([s["tokens"] for s in train])
    vocab_size = len(vocab)
    max_len = args.max_len

    def encode_batch(items):
        return torch.tensor([encode_tokens(s["tokens"], vocab, max_len) for s in items], dtype=torch.long)

    class NextActionLSTM(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Embedding(vocab_size, args.embed, padding_idx=vocab[PAD])
            self.lstm = nn.LSTM(args.embed, args.hidden, batch_first=True)
            self.head = nn.Linear(args.hidden, vocab_size)

        def forward(self, x):
            emb = self.embed(x)
            out, _ = self.lstm(emb)
            return self.head(out)

    model = NextActionLSTM()
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.CrossEntropyLoss(ignore_index=vocab[PAD])
    xb = encode_batch(train)

    model.train()
    for ep in range(args.epochs):
        opt.zero_grad()
        logits = model(xb[:, :-1])
        loss = loss_fn(logits.reshape(-1, vocab_size), xb[:, 1:].reshape(-1))
        loss.backward()
        opt.step()
        if (ep + 1) % 5 == 0:
            print(f"epoch {ep + 1}: loss={loss.item():.4f}")

    model.eval()

    def session_nll(items):
        scores = []
        with torch.no_grad():
            x = encode_batch(items)
            logits = model(x)
            logp = torch.log_softmax(logits, dim=-1)
            for b in range(x.shape[0]):
                nlls = []
                for t in range(1, max_len):
                    tok = x[b, t].item()
                    if tok == vocab[PAD]:
                        break
                    nlls.append(-logp[b, t - 1, tok].item())
                scores.append(max(nlls) if nlls else 0.0)
        return np.array(scores)

    val_scores = session_nll(val)
    threshold = float(np.percentile(val_scores, 90)) if len(val_scores) else 1.0

    metrics = {"n_train": len(train), "n_val": len(val), "n_redteam": len(redteam),
               "threshold": threshold, "vocab_size": vocab_size}
    if redteam:
        rt_scores = session_nll(redteam)
        tp = int((rt_scores >= threshold).sum()); fn = int((rt_scores < threshold).sum())
        fp = int((val_scores >= threshold).sum()); tn = int((val_scores < threshold).sum())
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        metrics["lstm"] = {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}

    def features(items):
        rows = []
        for s in items:
            toks = s["tokens"]; n = len(toks) or 1
            ext = sum(1 for t in toks if "external_send" in t or "destructive" in t)
            uniq = len(set(toks))
            rows.append([n, ext / n, uniq / n])
        return np.array(rows) if items else np.zeros((0, 3))

    if len(train) >= 5:
        iso = IsolationForest(n_estimators=200, contamination=0.2, random_state=args.seed)
        iso.fit(features(train))
        if redteam:
            pred = iso.predict(features(redteam))
            metrics["isolation_forest"] = {"recall_on_redteam": float((pred == -1).mean())}

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    dummy = torch.zeros(1, max_len, dtype=torch.long)
    torch.onnx.export(
        model, dummy, str(ARTIFACTS / "lstm_nextaction.onnx"),
        input_names=["tokens"], output_names=["logits"], dynamic_axes=None, opset_version=13,
    )
    (ARTIFACTS / "vocab.json").write_text(json.dumps(vocab), encoding="utf-8")
    (ARTIFACTS / "model_meta.json").write_text(
        json.dumps({"max_len": max_len, "threshold": threshold}), encoding="utf-8"
    )
    (ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    flat = {"threshold": threshold, "vocab_size": vocab_size}
    if "lstm" in metrics:
        flat.update({f"lstm_{k}": v for k, v in metrics["lstm"].items()})
    if "isolation_forest" in metrics:
        flat.update({f"iso_{k}": v for k, v in metrics["isolation_forest"].items()})
    mlflow.log_metrics({k: float(v) for k, v in flat.items()})
    mlflow.log_artifact(str(ARTIFACTS / "lstm_nextaction.onnx"))
    mlflow.log_artifact(str(ARTIFACTS / "metrics.json"))
    mlflow.end_run()

    print("Saved artifacts to", ARTIFACTS)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
