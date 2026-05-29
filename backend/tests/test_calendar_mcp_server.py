"""Tests for the Google Calendar MCP server."""

from app.mcp_servers.calendar.server import _normalize_event, create_calendar_server


def test_normalize_timed_calendar_event():
    raw_event = {
        "id": "evt_123",
        "summary": "ByteOps project sync",
        "start": {"dateTime": "2026-05-26T10:00:00+05:00"},
        "end": {"dateTime": "2026-05-26T10:30:00+05:00"},
        "location": "Google Meet",
        "hangoutLink": "https://meet.google.com/abc-defg-hij",
        "attendees": [
            {"email": "duarizwan098@gmail.com"},
            {"email": "byteops00@gmail.com"},
        ],
        "status": "confirmed",
    }

    normalized = _normalize_event(raw_event, calendar_id="primary", calendar_name="Primary")

    assert normalized == {
        "id": "evt_123",
        "calendar_id": "primary",
        "calendar_name": "Primary",
        "title": "ByteOps project sync",
        "description": "",
        "start": "2026-05-26T10:00:00+05:00",
        "end": "2026-05-26T10:30:00+05:00",
        "location": "Google Meet",
        "meeting_link": "https://meet.google.com/abc-defg-hij",
        "attendees": ["duarizwan098@gmail.com", "byteops00@gmail.com"],
        "status": "confirmed",
        "html_link": "",
    }


def test_normalize_all_day_calendar_event():
    raw_event = {
        "id": "evt_all_day",
        "summary": "Submission day",
        "start": {"date": "2026-05-26"},
        "end": {"date": "2026-05-27"},
        "status": "confirmed",
    }

    normalized = _normalize_event(raw_event, calendar_id="primary", calendar_name="Primary")

    assert normalized["title"] == "Submission day"
    assert normalized["start"] == "2026-05-26"
    assert normalized["end"] == "2026-05-27"
    assert normalized["location"] == ""
    assert normalized["meeting_link"] == ""
    assert normalized["attendees"] == []


def test_create_calendar_server_registers_expected_tools():
    server = create_calendar_server(access_token="token")

    tool_names = {tool.name for tool in server._tool_manager.list_tools()}

    assert tool_names == {
        "list_events",
        "search_events",
        "get_event",
        "create_event",
        "update_event",
        "delete_event",
        "quick_add",
    }
