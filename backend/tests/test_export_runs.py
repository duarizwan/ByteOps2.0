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
