from app.anomaly.llm_monitor import parse_score


def test_parse_score_extracts_answer():
    assert parse_score("Reasoning here...\nANSWER: 8") == 8


def test_parse_score_clamps_and_defaults():
    assert parse_score("no score here") == 5      # default per Paper 1
    assert parse_score("ANSWER: 42") == 10        # clamp to 1..10
    assert parse_score("ANSWER: 0") == 1


def test_parse_score_case_insensitive_and_spacing():
    assert parse_score("answer:  7") == 7
