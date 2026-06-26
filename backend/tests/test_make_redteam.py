"""The synthetic red-team generator is deterministic and well-formed."""

from scripts.make_redteam import generate

VALID_TOKENS = {
    "plan|none|completed", "route|none|completed", "tool_call|read|completed",
    "tool_call|write|completed", "tool_call|external_send|completed",
    "tool_call|destructive|completed", "verify|none|completed", "final|none|completed",
}


def test_generate_count_and_labels():
    runs = generate(25, seed=42)
    assert len(runs) == 25
    assert all(r["label"] == "redteam" for r in runs)
    assert all(r["run_id"].startswith("synthetic-redteam-") for r in runs)


def test_tokens_use_real_vocabulary():
    for r in generate(14, seed=1):
        assert r["tokens"], "no empty sequences"
        for tok in r["tokens"]:
            assert tok in VALID_TOKENS, f"unexpected token {tok}"


def test_deterministic_with_seed():
    assert generate(10, seed=7) == generate(10, seed=7)


def test_contains_anomalous_signals():
    runs = generate(14, seed=3)
    flat = [t for r in runs for t in r["tokens"]]
    # the anomalous signals the detectors key on must appear across the set
    assert "tool_call|external_send|completed" in flat
    assert "tool_call|destructive|completed" in flat
