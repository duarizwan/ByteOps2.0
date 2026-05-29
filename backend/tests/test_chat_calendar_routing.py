"""Tests for Calendar intent routing and capability prompts."""

from app.agents.orchestrator import build_system_prompt, detect_intent


def test_detect_intent_routes_direct_calendar_prompt_to_calendar():
    assert detect_intent("What's on my calendar today?") == "calendar"


def test_detect_intent_routes_meetings_prompt_to_calendar():
    assert detect_intent("Find my meetings this week") == "calendar"


def test_build_system_prompt_lists_full_calendar_capabilities():
    prompt = build_system_prompt(["calendar"])

    assert "Google Calendar" in prompt
    assert "list_events" in prompt
    assert "search_events" in prompt
    assert "create_event" in prompt
    assert "update_event" in prompt
    assert "delete_event" in prompt
    assert "quick_add" in prompt
