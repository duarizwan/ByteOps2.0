"""Score agent runs for anomalies using an offline-trained ONNX model.

Designed to never raise into the request path: if artifacts are missing or
inference fails, scoring returns None and the run proceeds unaffected.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.anomaly.tokenizer import encode_tokens, run_to_tokens

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parent / "artifacts"


class AnomalyScorer:
    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self._dir = Path(artifacts_dir) if artifacts_dir else _DEFAULT_DIR
        self._session = None
        self._vocab: dict[str, int] = {}
        self._meta: dict = {}
        self._load()

    @property
    def available(self) -> bool:
        return self._session is not None

    def _load(self) -> None:
        onnx_path = self._dir / "lstm_nextaction_v1.onnx"
        vocab_path = self._dir / "vocab.json"
        meta_path = self._dir / "model_meta.json"
        if not (onnx_path.exists() and vocab_path.exists() and meta_path.exists()):
            logger.info("Anomaly artifacts not found in %s; scoring disabled.", self._dir)
            return
        try:
            import onnxruntime as ort

            self._vocab = json.loads(vocab_path.read_text(encoding="utf-8"))
            self._meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._session = ort.InferenceSession(
                str(onnx_path), providers=["CPUExecutionProvider"]
            )
        except Exception as exc:  # noqa: BLE001 - never break startup
            logger.warning("Failed to load anomaly model: %s", exc)
            self._session = None

    def score_run(self, steps: list[dict]) -> dict | None:
        """Return {anomaly_score, step_scores, flagged} or None if unavailable."""
        if not self.available or not steps:
            return None
        try:
            import numpy as np

            max_len = int(self._meta.get("max_len", 12))
            threshold = float(self._meta.get("threshold", 0.0))
            tokens = run_to_tokens(steps)
            ids = encode_tokens(tokens, self._vocab, max_len)
            arr = np.asarray([ids], dtype=np.int64)
            (logits,) = self._session.run(["logits"], {"tokens": arr})
            logits = logits[0]  # [max_len, vocab_size]

            # log-softmax along vocab axis
            m = logits.max(axis=-1, keepdims=True)
            log_probs = logits - m - np.log(np.exp(logits - m).sum(axis=-1, keepdims=True))

            n = min(len(steps), max_len)
            nlls: list[float] = []
            for i in range(1, n):
                nlls.append(float(-log_probs[i - 1, ids[i]]))
            mean_nll = float(np.mean(nlls)) if nlls else 0.0

            step_scores: dict[str, float] = {}
            for idx, step in enumerate(steps):
                sid = str(step.get("id", idx))
                if idx == 0 or idx >= max_len:
                    step_scores[sid] = round(mean_nll, 4)
                else:
                    step_scores[sid] = round(float(-log_probs[idx - 1, ids[idx]]), 4)

            session_score = max(step_scores.values()) if step_scores else 0.0
            return {
                "anomaly_score": round(float(session_score), 4),
                "step_scores": step_scores,
                "flagged": bool(session_score >= threshold),
            }
        except Exception as exc:  # noqa: BLE001 - never break the run
            logger.warning("Anomaly scoring failed: %s", exc)
            return None
