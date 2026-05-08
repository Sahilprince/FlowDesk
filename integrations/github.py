import os
from datetime import datetime, timezone
from typing import Any


def get_github_connection_status() -> dict[str, Any]:
    configured = bool(os.getenv("GITHUB_CLIENT_ID") and os.getenv("GITHUB_CLIENT_SECRET"))
    token_present = bool(os.getenv("GITHUB_ACCESS_TOKEN"))

    state = "connected" if configured and token_present else "not_connected"
    next_step = None
    if not configured:
        next_step = "Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."
    elif not token_present:
        next_step = "Click Connect GitHub and approve FlowDesk access."

    return {
        "service": "github",
        "label": "GitHub",
        "state": state,
        "auth_type": "github_oauth",
        "configured": configured,
        "token_present": token_present,
        "scopes": ["repo", "read:user", "user:email"],
        "next_step": next_step,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def github_issue_create(repository: str, title: str, body: str) -> dict[str, Any]:
    status = get_github_connection_status()
    return {
        "tool": "github_issue_create",
        "repository": repository,
        "title": title,
        "body": body,
        "status": "ready" if status["state"] == "connected" else "stub",
        "integration": status,
        "requires_approval": True,
        "message": (
            "GitHub adapter is connected and ready to create issues after approval."
            if status["state"] == "connected"
            else "GitHub adapter scaffolded. After approval this would call the GitHub API once OAuth is connected."
        ),
    }
