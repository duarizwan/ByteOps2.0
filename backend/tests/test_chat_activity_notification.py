"""Tests for chat-created activity notification summaries."""

from app.api.chat import _build_activity_notification_payload


def test_activity_notification_payload_uses_attention_title_not_user_query():
    payload = _build_activity_notification_payload(
        source_tool="gmail",
        user_message="check my gmail for anything important",
        response_text="The CFO shared a contract update that needs attention.",
    )

    assert payload["title"] == "The CFO shared a contract update that needs attention."
    assert payload["title"] != "check my gmail for anything important"
    assert payload["priority"] == "high"
    assert payload["metadata"]["from_chat"] is True
    assert payload["metadata"]["category"] == "alert"
    assert payload["metadata"]["attention_title"] == payload["title"]


def test_activity_notification_payload_classifies_action_items_as_tasks():
    payload = _build_activity_notification_payload(
        source_tool="slack",
        user_message="check slack",
        response_text="Maya asked you to review the launch checklist by Friday.",
    )

    assert payload["metadata"]["category"] == "task"
    assert payload["metadata"]["action_required"] is True
    assert payload["priority"] == "high"


def test_activity_notification_payload_removes_markdown_markers():
    payload = _build_activity_notification_payload(
        source_tool="gmail",
        user_message="check gmail",
        response_text="*CFO* | contract - update. - Review | terms *today*.",
    )

    assert payload["title"] == "CFO contract update."
    assert payload["content"] == "CFO contract update. Review terms today."
    assert "*" not in payload["title"]
    assert "-" not in payload["title"]
    assert "|" not in payload["title"]
    assert "*" not in payload["content"]
    assert "-" not in payload["content"]
    assert "|" not in payload["content"]
