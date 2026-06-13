from scripts.generate_dataset import generate, ANOMALY_TYPES


def test_generate_balanced_with_types_and_injected_index():
    runs = generate(n_normal=20, n_anom_per_type=3, seed=42)
    labels = [r["label"] for r in runs]
    assert labels.count("normal") == 20
    anom = [r for r in runs if r["label"] == "redteam"]
    assert len(anom) == 3 * len(ANOMALY_TYPES)
    for r in anom:
        assert r["anomaly_type"] in ANOMALY_TYPES
        assert 0 <= r["anomalous_step_index"] < len(r["steps"])
        assert all("step_type" in s for s in r["steps"])


def test_generate_is_deterministic():
    assert generate(5, 2, seed=7) == generate(5, 2, seed=7)
