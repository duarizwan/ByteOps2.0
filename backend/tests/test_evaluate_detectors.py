"""Unit tests for the detector-comparison metric helpers (pure, no ML deps)."""

import numpy as np

from scripts.evaluate_detectors import best_f1, partial_auroc


def test_partial_auroc_perfect_separation():
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.9, 0.8])  # positives score highest
    assert partial_auroc(labels, scores) == 1.0


def test_partial_auroc_nan_when_one_class():
    labels = np.array([0, 0, 0])
    scores = np.array([0.1, 0.2, 0.3])
    assert np.isnan(partial_auroc(labels, scores))


def test_best_f1_perfect():
    labels = np.array([0, 0, 1, 1])
    scores = np.array([0.1, 0.2, 0.9, 0.8])
    f1, prec, rec, thr = best_f1(labels, scores)
    assert f1 == 1.0
    assert prec == 1.0
    assert rec == 1.0
