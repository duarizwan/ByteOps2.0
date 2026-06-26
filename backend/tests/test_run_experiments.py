"""Unit tests for the experiment-suite helpers (pure, no ML deps)."""

import numpy as np

from scripts.run_experiments import _shuffle_tokens, mean_ci


def test_mean_ci_single_value_has_zero_width():
    m, c = mean_ci([0.5])
    assert m == 0.5
    assert c == 0.0


def test_mean_ci_computes_mean_and_positive_ci():
    m, c = mean_ci([1.0, 2.0, 3.0])
    assert m == 2.0
    assert c > 0.0


def test_shuffle_tokens_preserves_multiset_but_reorders_possible():
    seqs = [{"tokens": ["a", "b", "c", "d", "e"], "label": "normal"}]
    rng = np.random.default_rng(0)
    out = _shuffle_tokens(seqs, rng)
    # same tokens (as a multiset), original untouched
    assert sorted(out[0]["tokens"]) == ["a", "b", "c", "d", "e"]
    assert seqs[0]["tokens"] == ["a", "b", "c", "d", "e"]
    assert out[0]["label"] == "normal"
