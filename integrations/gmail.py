import os
from datetime import datetime, timezone
from typing import Any


def get_gmail_connection_status() -> dict[str, Any]:
    configured = bool(
        os.getenv("GOOGLE_CLIENT_ID")
        and os.getenv("GOOGLE_CLIENT_SECRET")
        and os.getenv("GOOGLE_REDIRECT_URI")
    )
    token_present = bool(os.getenv("GOOGLE_GMAIL_REFRESH_TOKEN"))

    state = "connected" if configured and token_present else "not_connected"
    next_step = None
    if not configured:
        next_step = "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI."
    elif not token_present:
        next_step = "Complete Google OAuth and store GOOGLE_GMAIL_REFRESH_TOKEN."

    return {
        "service": "gmail",
        "label": "Gmail",
        "state": state,
        "auth_type": "google_oauth",
        "provider": "google",
        "configured": configured,
        "token_present": token_present,
        "scopes": [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ],
        "connectable": configured,
        "next_step": next_step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def gmail_read_messages(query: str) -> dict[str, Any]:
    status = get_gmail_connection_status()
    return {
        "tool": "gmail_read",
        "query": query,
        "status": "ready" if status["state"] == "connected" else "stub",
        "integration": status,
        "message": (
            "Gmail adapter is connected and ready for live API calls."
            if status["state"] == "connected"
            else "Gmail adapter scaffolded. Replace this stub with live Gmail API calls after OAuth is connected."
        ),
    }


def gmail_send_message(to: str, subject: str, body: str) -> dict[str, Any]:
    status = get_gmail_connection_status()
    return {
        "tool": "gmail_send",
        "to": to,
        "subject": subject,
        "body": body,
        "status": "ready" if status["state"] == "connected" else "stub",
        "integration": status,
        "requires_approval": True,
        "message": (
            "Gmail adapter is connected and ready to send after approval."
            if status["state"] == "connected"
            else "Gmail adapter scaffolded. After approval this would call Gmail send once OAuth is connected."
        ),
    }
