from scripts.generate_dataset import generate, ANOMALY_TYPES, _AUTHORIZING_INTENT


def test_generate_has_normals_subtle_positives_and_hard_negatives():
    runs = generate(n_normal=20, n_anom_per_type=3, seed=42)
    normals = [r for r in runs if r["kind"] == "normal"]
    subtle = [r for r in runs if r["kind"] == "subtle_positive"]
    hard = [r for r in runs if r["kind"] == "hard_negative"]

    assert len(normals) == 20 and all(r["label"] == "normal" for r in normals)
    # subtle positives = read-intent + injected risky action -> anomalous
    assert len(subtle) == 3 * len(ANOMALY_TYPES)
    for r in subtle:
        assert r["label"] == "redteam"
        assert r["anomaly_type"] in ANOMALY_TYPES
        assert 0 <= r["anomalous_step_index"] < len(r["steps"])
    # hard negatives = authorizing intent + the SAME risky action -> normal
    assert len(hard) == 3 * len(_AUTHORIZING_INTENT)
    assert all(r["label"] == "normal" for r in hard)


def test_hard_negative_and_subtle_positive_share_action_but_differ_by_intent():
    runs = generate(n_normal=5, n_anom_per_type=4, seed=1)
    # exfiltration: forward_email appears in BOTH a normal (authorized) and an anomalous run
    sub = [r for r in runs if r["kind"] == "subtle_positive" and r["anomaly_type"] == "exfiltration"][0]
    hard = [r for r in runs if r["kind"] == "hard_negative" and "forward" in r["intent"]][0]
    assert any(s["name"] == "forward_email" for s in sub["steps"])   # anomalous
    assert any(s["name"] == "forward_email" for s in hard["steps"])  # normal
    assert sub["label"] == "redteam" and hard["label"] == "normal"   # only intent differs


def test_generate_is_deterministic():
    assert generate(5, 2, seed=7) == generate(5, 2, seed=7)
