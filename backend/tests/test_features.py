from app.anomaly.features import infer_tool, action_category
from app.anomaly.features import extract_step_features, NUMERIC_FEATURES


def test_infer_tool_from_action_name():
    assert infer_tool("send_email") == "gmail"
    assert infer_tool("create_event") == "calendar"
    assert infer_tool("merge_pr") == "github"
    assert infer_tool("send_message") == "slack"
    assert infer_tool("transition_issue") == "jira"
    assert infer_tool("upload_file") == "dropbox"
    assert infer_tool("initial_plan") == "none"


def test_action_category():
    assert action_category("forward_email") == "external"
    assert action_category("delete_event") == "destructive"
    assert action_category("create_issue") == "write"
    assert action_category("search_emails") == "read"
    assert action_category("initial_plan") == "none"


def _run():
    return [
        {"step_type": "plan", "name": "initial_plan", "status": "completed"},
        {"step_type": "tool_call", "name": "search_emails", "status": "completed"},
        {"step_type": "tool_call", "name": "forward_email", "status": "completed"},
        {"step_type": "final", "name": "final", "status": "completed"},
    ]


def test_extract_step_features_categoricals_and_numerics():
    steps = _run()
    f = extract_step_features(steps, idx=2)  # the forward_email step
    assert f["step_type"] == "tool_call"
    assert f["tool_name"] == "gmail"
    assert f["action_category"] == "external"
    assert f["is_external_domain"] == 1
    assert 0.0 <= f["position_frac"] <= 1.0
    for name in NUMERIC_FEATURES:
        assert isinstance(f[name], (int, float))


def test_cross_tool_flag():
    steps = _run()  # gmail-only here -> not cross-tool
    assert extract_step_features(steps, idx=1)["is_cross_tool_action"] == 0
