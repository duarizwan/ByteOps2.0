"""Google Calendar MCP Server — full CRUD.

Exposes Google Calendar API capabilities as MCP tools via FastMCP.
Credentials are injected as environment variables by the Calendar Agent.

Tools (Reading):
  - list_events      — list events in a time range
  - search_events    — search events by text
  - get_event        — get full details of one event

Tools (Writing):
  - create_event     — create a new event
  - update_event     — update an existing event (patch — only changed fields)
  - delete_event     — permanently delete an event
  - quick_add        — create event from natural-language string (e.g. "Lunch with Alice tomorrow 1pm")
"""

from __future__ import annotations

import os
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP


# ── Helpers ────────────────────────────────────────────────────────────────────

def _event_time(value: dict[str, Any] | None) -> str:
    if not value:
        return ""
    return value.get("dateTime") or value.get("date") or ""


def _meeting_link(event: dict[str, Any]) -> str:
    if event.get("hangoutLink"):
        return event["hangoutLink"]
    for entry in event.get("conferenceData", {}).get("entryPoints", []):
        uri = entry.get("uri")
        if uri:
            return uri
    return ""


def _normalize_event(event: dict[str, Any], calendar_id: str, calendar_name: str) -> dict[str, Any]:
    attendees = [a["email"] for a in event.get("attendees", []) if a.get("email")]
    return {
        "id": event.get("id", ""),
        "calendar_id": calendar_id,
        "calendar_name": calendar_name,
        "title": event.get("summary") or "(no title)",
        "description": event.get("description", ""),
        "start": _event_time(event.get("start")),
        "end": _event_time(event.get("end")),
        "location": event.get("location", ""),
        "meeting_link": _meeting_link(event),
        "attendees": attendees,
        "status": event.get("status", ""),
        "html_link": event.get("htmlLink", ""),
    }


def _format_http_error(e: HttpError) -> str:
    status = e.resp.status if e.resp else "unknown"
    if status == 403:
        return (
            f"Permission denied (403). Your Calendar connection may have read-only access. "
            f"Please reconnect Google Calendar in Settings → Connections to grant full access."
        )
    if status == 401:
        return (
            f"Authentication expired (401). Please reconnect Google Calendar in "
            f"Settings → Connections."
        )
    return f"Google Calendar API error {status}: {e}"


# ── CalendarClient ─────────────────────────────────────────────────────────────

class CalendarClient:
    """Wrapper around the Google Calendar API v3 service."""

    def __init__(
        self,
        access_token: str,
        refresh_token: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> None:
        creds = Credentials(
            token=access_token,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
        )
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        self.service = build("calendar", "v3", credentials=creds, cache_discovery=False)

    def _calendar_name(self, calendar_id: str) -> str:
        try:
            cal = self.service.calendarList().get(calendarId=calendar_id).execute()
            return cal.get("summary") or calendar_id
        except Exception:
            return "Primary" if calendar_id == "primary" else calendar_id

    # ── Reading ───────────────────────────────────────────────────────────────

    def list_events(self, time_min: str, time_max: str,
                    calendar_id: str = "primary", max_results: int = 10) -> list[dict[str, Any]]:
        try:
            resp = (
                self.service.events()
                .list(calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
                      maxResults=max_results, singleEvents=True, orderBy="startTime")
                .execute()
            )
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        name = self._calendar_name(calendar_id)
        return [_normalize_event(ev, calendar_id, name) for ev in resp.get("items", [])]

    def search_events(self, query: str, time_min: str, time_max: str,
                      calendar_id: str = "primary", max_results: int = 10) -> list[dict[str, Any]]:
        try:
            resp = (
                self.service.events()
                .list(calendarId=calendar_id, q=query, timeMin=time_min, timeMax=time_max,
                      maxResults=max_results, singleEvents=True, orderBy="startTime")
                .execute()
            )
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        name = self._calendar_name(calendar_id)
        return [_normalize_event(ev, calendar_id, name) for ev in resp.get("items", [])]

    def get_event(self, event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
        try:
            ev = self.service.events().get(calendarId=calendar_id, eventId=event_id).execute()
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        name = self._calendar_name(calendar_id)
        return _normalize_event(ev, calendar_id, name)

    # ── Writing ───────────────────────────────────────────────────────────────

    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        timezone: str = "UTC",
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a new event. start_time / end_time must be ISO 8601 datetime strings."""
        # Support all-day events: if the string has no 'T', treat as date-only
        def _time_field(dt: str) -> dict[str, str]:
            if "T" in dt:
                return {"dateTime": dt, "timeZone": timezone}
            return {"date": dt}

        body: dict[str, Any] = {
            "summary": title,
            "start": _time_field(start_time),
            "end": _time_field(end_time),
        }
        if description:
            body["description"] = description
        if location:
            body["location"] = location
        if attendees:
            body["attendees"] = [{"email": e} for e in attendees]

        try:
            ev = self.service.events().insert(calendarId=calendar_id, body=body,
                                              sendUpdates="all" if attendees else "none").execute()
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        name = self._calendar_name(calendar_id)
        return _normalize_event(ev, calendar_id, name)

    def update_event(
        self,
        event_id: str,
        title: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        timezone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Patch an existing event — only provided fields are changed."""
        patch: dict[str, Any] = {}
        if title is not None:
            patch["summary"] = title
        if description is not None:
            patch["description"] = description
        if location is not None:
            patch["location"] = location

        def _time_field(dt: str, tz: str | None) -> dict[str, str]:
            if "T" in dt:
                return {"dateTime": dt, "timeZone": tz or "UTC"}
            return {"date": dt}

        if start_time is not None:
            patch["start"] = _time_field(start_time, timezone)
        if end_time is not None:
            patch["end"] = _time_field(end_time, timezone)

        try:
            ev = self.service.events().patch(calendarId=calendar_id, eventId=event_id,
                                             body=patch).execute()
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        name = self._calendar_name(calendar_id)
        return _normalize_event(ev, calendar_id, name)

    def delete_event(self, event_id: str, calendar_id: str = "primary") -> dict[str, str]:
        try:
            self.service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        return {"status": "deleted", "event_id": event_id}

    def quick_add(self, text: str, calendar_id: str = "primary") -> dict[str, Any]:
        """Create an event from a natural-language string like 'Lunch with Alice tomorrow 1pm'."""
        try:
            ev = self.service.events().quickAdd(calendarId=calendar_id, text=text).execute()
        except HttpError as e:
            raise RuntimeError(_format_http_error(e)) from e
        name = self._calendar_name(calendar_id)
        return _normalize_event(ev, calendar_id, name)


# ── FastMCP server ─────────────────────────────────────────────────────────────

def create_calendar_server(
    access_token: str,
    refresh_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
) -> FastMCP:
    server = FastMCP("ByteOps Calendar Agent")
    client = CalendarClient(access_token, refresh_token, client_id, client_secret)

    # ── Reading tools ─────────────────────────────────────────────────────────

    @server.tool()
    def list_events(
        time_min: str,
        time_max: str,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """List calendar events in a time range.

        Args:
          time_min: ISO 8601 lower bound e.g. '2025-05-28T00:00:00Z'
          time_max: ISO 8601 upper bound e.g. '2025-06-04T00:00:00Z'
          calendar_id: calendar ID, default 'primary'
          max_results: max events to return
        """
        return client.list_events(time_min, time_max, calendar_id, max_results)

    @server.tool()
    def search_events(
        query: str,
        time_min: str,
        time_max: str,
        calendar_id: str = "primary",
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search calendar events by text in a time range.

        Args:
          query: text to search in event title, description, location
          time_min: ISO 8601 lower bound
          time_max: ISO 8601 upper bound
          calendar_id: calendar ID, default 'primary'
          max_results: max results
        """
        return client.search_events(query, time_min, time_max, calendar_id, max_results)

    @server.tool()
    def get_event(event_id: str, calendar_id: str = "primary") -> dict[str, Any]:
        """Get full details of a single calendar event by its ID.

        Args:
          event_id: the event ID from list_events or search_events
          calendar_id: calendar ID, default 'primary'
        """
        return client.get_event(event_id, calendar_id)

    # ── Writing tools ─────────────────────────────────────────────────────────

    @server.tool()
    def create_event(
        title: str,
        start_time: str,
        end_time: str,
        timezone: str = "UTC",
        description: str = "",
        location: str = "",
        attendees: list[str] | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Create a new calendar event.

        Args:
          title: event title / summary
          start_time: ISO 8601 datetime e.g. '2025-06-01T10:00:00' or all-day '2025-06-01'
          end_time: ISO 8601 datetime e.g. '2025-06-01T11:00:00' or all-day '2025-06-02'
          timezone: IANA timezone name e.g. 'Asia/Karachi', 'America/New_York', 'UTC' (default 'UTC')
          description: optional event notes
          location: optional venue or address
          attendees: optional list of attendee email addresses
          calendar_id: which calendar to create in, default 'primary'
        Returns the created event with id, title, start, end, and link.
        IMPORTANT: Confirm details with the user before creating.
        """
        return client.create_event(title, start_time, end_time, timezone,
                                   description, location, attendees, calendar_id)

    @server.tool()
    def update_event(
        event_id: str,
        title: str | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        timezone: str | None = None,
        description: str | None = None,
        location: str | None = None,
        calendar_id: str = "primary",
    ) -> dict[str, Any]:
        """Update an existing calendar event. Only provided fields are changed.

        Args:
          event_id: event ID from list_events or search_events
          title: new title (omit to keep existing)
          start_time: new ISO 8601 start datetime (omit to keep existing)
          end_time: new ISO 8601 end datetime (omit to keep existing)
          timezone: IANA timezone for the new times (omit to keep existing)
          description: new description (omit to keep existing)
          location: new location (omit to keep existing)
          calendar_id: calendar ID, default 'primary'
        IMPORTANT: Confirm changes with the user before updating.
        """
        return client.update_event(event_id, title, start_time, end_time,
                                   timezone, description, location, calendar_id)

    @server.tool()
    def delete_event(event_id: str, calendar_id: str = "primary") -> dict[str, str]:
        """Permanently delete a calendar event.

        Args:
          event_id: event ID from list_events or search_events
          calendar_id: calendar ID, default 'primary'
        IMPORTANT: This cannot be undone. Always confirm with the user first.
        """
        return client.delete_event(event_id, calendar_id)

    @server.tool()
    def quick_add(text: str, calendar_id: str = "primary") -> dict[str, Any]:
        """Create an event from a natural-language string. Google parses the text.

        Args:
          text: human-readable event string e.g. 'Lunch with Alice tomorrow 1pm' or
                'Team standup every Monday 9am'
          calendar_id: calendar ID, default 'primary'
        Returns the created event details.
        """
        return client.quick_add(text, calendar_id)

    return server


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    access_token = os.environ.get("CALENDAR_ACCESS_TOKEN", "")
    refresh_token = os.environ.get("CALENDAR_REFRESH_TOKEN")
    client_id = os.environ.get("CALENDAR_CLIENT_ID")
    client_secret = os.environ.get("CALENDAR_CLIENT_SECRET")

    if not access_token:
        print("ERROR: CALENDAR_ACCESS_TOKEN env var is required.", file=sys.stderr, flush=True)
        sys.exit(1)

    server = create_calendar_server(access_token, refresh_token, client_id, client_secret)
    server.run()
