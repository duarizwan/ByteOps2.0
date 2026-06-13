"""Run-level anomaly score + per-step attention (for the run-graph heat), from the
trained BiLSTM+Attention ONNX model. Never raises into the request path: if the
model is missing or inference fails, returns None and the run is unaffected.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.anomaly.features import CATEGORICAL_FIELDS, encode_run

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parent / "artifacts"


class AttentionScorer:
    def __init__(self, artifacts_dir: Path | None = None) -> None:
        self._dir = Path(artifacts_dir) if artifacts_dir else _DEFAULT_DIR
        self._session = None
        self._meta: dict = {}
        self._load()

    @property
    def available(self) -> bool:
        return self._session is not None

    def _load(self) -> None:
        onnx_path = self._dir / "clf_bilstm_attn.onnx"
        meta_path = self._dir / "clf_bilstm_attn_meta.json"
        if not (onnx_path.exists() and meta_path.exists()):
            logger.info("Attention model not found in %s; attention scoring disabled.", self._dir)
            return
        try:
            import onnxruntime as ort
            self._meta = json.loads(meta_path.read_text(encoding="utf-8"))
            self._session = ort.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to load attention model: %s", exc)
            self._session = None

    def score_run(self, steps: list[dict]) -> dict | None:
        """Return {anomaly_score(0-10), step_scores{id: attn}, flagged, reasoning} or None."""
        if not self.available or not steps:
            return None
        try:
            import numpy as np

            vocabs = self._meta["vocabs"]
            max_len = int(self._meta.get("max_len", 20))
            threshold = float(self._meta.get("threshold", 0.5))
            enc = encode_run(steps, vocabs, max_len)
            feeds = {f: np.asarray([enc["cat"][f]], dtype=np.int64) for f in CATEGORICAL_FIELDS}
            feeds["num"] = np.asarray([enc["num"]], dtype=np.float32)
            feeds["mask"] = np.asarray([enc["mask"]], dtype=np.float32)
            logit, attn = self._session.run(["logit", "attn"], feeds)
            prob = float(1.0 / (1.0 + np.exp(-logit[0])))
            attn = np.asarray(attn[0])  # [max_len]
            # map attention onto real steps (truncated to max_len)
            n = min(len(steps), max_len)
            step_scores = {}
            for i in range(n):
                sid = str(steps[i].get("id", i))
                step_scores[sid] = round(float(attn[i]), 4)
            top = max(range(n), key=lambda i: attn[i]) if n else 0
            top_name = steps[top].get("name", "?") if n else "?"
            return {
                "anomaly_score": round(prob * 10.0, 4),
                "step_scores": step_scores,
                "flagged": bool(prob >= threshold),
                "reasoning": f"Model attended most to step '{top_name}' (suspicion {prob:.2f}).",
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("Attention scoring failed: %s", exc)
            return None
