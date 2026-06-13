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
        onnx_path = self._dir / "lstm_nextaction.onnx"
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
        if not self.available:
            return None
        return None  # real inference added in a later task
