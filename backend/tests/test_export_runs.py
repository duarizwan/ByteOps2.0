from scripts.export_runs import run_record_to_sequence


def test_run_record_to_sequence_shape():
    record = {
        "id": "r1",
        "data_label": "normal",
        "steps": [
            {"id": "a", "step_type": "plan", "name": "initial_plan", "status": "completed"},
            {"id": "b", "step_type": "tool_call", "name": "send_email", "status": "completed"},
        ],
    }
    seq = run_record_to_sequence(record)
    assert seq["run_id"] == "r1"
    assert seq["label"] == "normal"
    assert seq["tokens"] == ["plan|none|completed", "tool_call|external_send|completed"]


def test_export_includes_rich_steps_and_type():
    record = {
        "id": "r1", "data_label": "redteam", "intent": "general",
        "metadata": {"anomaly_type": "exfiltration"},
        "steps": [
            {"id": "a", "step_type": "plan", "name": "initial_plan", "status": "completed"},
            {"id": "b", "step_type": "tool_call", "name": "forward_email", "status": "completed"},
        ],
    }
    seq = run_record_to_sequence(record)
    assert seq["label"] == "redteam"
    assert seq["anomaly_type"] == "exfiltration"
    assert seq["steps"][1]["name"] == "forward_email"
    assert seq["tokens"][1] == "tool_call|external_send|completed"
