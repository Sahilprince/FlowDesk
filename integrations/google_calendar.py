import os
from datetime import datetime, timezone
from typing import Any


def get_google_calendar_connection_status() -> dict[str, Any]:
    configured = bool(
        os.getenv("GOOGLE_CLIENT_ID")
        and os.getenv("GOOGLE_CLIENT_SECRET")
        and os.getenv("GOOGLE_REDIRECT_URI")
    )
    token_present = bool(os.getenv("GOOGLE_CALENDAR_REFRESH_TOKEN"))

    state = "connected" if configured and token_present else "not_connected"
    next_step = None
    if not configured:
        next_step = "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI."
    elif not token_present:
        next_step = "Complete Google OAuth and store GOOGLE_CALENDAR_REFRESH_TOKEN."

    return {
        "service": "google_calendar",
        "label": "Google Calendar",
        "state": state,
        "auth_type": "google_oauth",
        "provider": "google",
        "configured": configured,
        "token_present": token_present,
        "scopes": [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        ],
        "connectable": configured,
        "next_step": next_step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def google_calendar_read_events(date_range: str) -> dict[str, Any]:
    status = get_google_calendar_connection_status()
    return {
        "tool": "calendar_read",
        "date_range": date_range,
        "status": "ready" if status["state"] == "connected" else "stub",
        "integration": status,
        "message": (
            "Google Calendar adapter is connected and ready for live API calls."
            if status["state"] == "connected"
            else "Calendar adapter scaffolded. Replace this stub with live Calendar API calls after OAuth is connected."
        ),
    }


def google_calendar_create_event(title: str, when: str, attendees: str) -> dict[str, Any]:
    status = get_google_calendar_connection_status()
    return {
        "tool": "calendar_create",
        "title": title,
        "when": when,
        "attendees": attendees,
        "status": "ready" if status["state"] == "connected" else "stub",
        "integration": status,
        "requires_approval": True,
        "message": (
            "Google Calendar adapter is connected and ready to create events after approval."
            if status["state"] == "connected"
            else "Calendar adapter scaffolded. After approval this would call Calendar create once OAuth is connected."
        ),
    }
