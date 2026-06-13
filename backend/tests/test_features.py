from app.anomaly.features import infer_tool, action_category


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
