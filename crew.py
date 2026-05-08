import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from integrations import (
    get_gmail_connection_status,
    get_google_calendar_connection_status,
    gmail_read_messages,
    gmail_send_message,
    google_calendar_create_event,
    google_calendar_read_events,
)

try:
    from crewai_tools import tool as crewai_tool
except ImportError:
    crewai_tool = None


def tool(name: str):
    """Small fallback so the file works even when CrewAI is not installed."""

    def decorator(fn):
        fn.tool_name = name
        return crewai_tool(name)(fn) if crewai_tool else fn

    return decorator


FLOWDESK_LLM_BASE_URL = os.getenv("FLOWDESK_LLM_BASE_URL", "http://localhost:8000/v1")
FLOWDESK_LLM_MODEL = os.getenv(
    "FLOWDESK_LLM_MODEL", "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
)
FLOWDESK_LLM_API_KEY = os.getenv("FLOWDESK_LLM_API_KEY", "unused")


@tool("gmail_read")
def gmail_read(query: str) -> dict[str, Any]:
    """Read emails from Gmail matching a query."""
    return gmail_read_messages(query)


@tool("gmail_send")
def gmail_send(to: str, subject: str, body: str) -> dict[str, Any]:
    """Draft and queue a Gmail email for approval."""
    return gmail_send_message(to=to, subject=subject, body=body)


@tool("calendar_read")
def calendar_read(date_range: str) -> dict[str, Any]:
    """Read calendar events for a date range."""
    return google_calendar_read_events(date_range)


@tool("calendar_create")
def calendar_create(title: str, when: str, attendees: str) -> dict[str, Any]:
    """Queue a calendar event creation for approval."""
    return google_calendar_create_event(title=title, when=when, attendees=attendees)


@tool("save_workflow")
def save_workflow(name: str, trigger: str, condition: str, action: str) -> dict[str, Any]:
    """Save a reusable workflow definition."""
    return {
        "tool": "save_workflow",
        "name": name,
        "trigger": trigger,
        "condition": condition,
        "action": action,
    }


def route_request(user_input: str) -> str:
    text = user_input.lower()

    workflow_markers = [
        "every time",
        "whenever",
        "automatically",
        "if ",
        "each ",
        "daily",
        "weekly",
        "when i get",
    ]
    status_markers = [
        "summarize",
        "show me",
        "what's on",
        "what is on",
        "check",
        "status",
        "read",
        "list",
    ]

    if any(marker in text for marker in workflow_markers):
        return "create_workflow"
    if any(marker in text for marker in status_markers):
        return "status_check"
    return "one_time_task"


def _today_bounds() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    return start.strftime("%Y/%m/%d"), end.strftime("%Y/%m/%d")


def _gmail_query_for_text(user_input: str) -> str:
    text = user_input.lower()
    start, end = _today_bounds()

    if "today" in text:
        return f"after:{start} before:{end}"
    if "yesterday" in text:
        dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = dt - timedelta(days=1)
        return f"after:{start_dt.strftime('%Y/%m/%d')} before:{start}"
    if "unread" in text:
        return "is:unread"
    return "newer_than:7d"


def _calendar_range_for_text(user_input: str) -> str:
    text = user_input.lower()
    if "today" in text:
        return "today"
    if "tomorrow" in text:
        return "tomorrow"
    if "this week" in text:
        return "this_week"
    return "upcoming"


def _extract_email_fields(user_input: str) -> tuple[str, str, str]:
    patterns = [
        re.compile(
            r"send\s+(?P<to>.+?)\s+an email\s+about\s+(?P<subject>.+)",
            re.I,
        ),
        re.compile(
            r"send\s+an email\s+to\s+(?P<to>.+?)\s+about\s+(?P<subject>.+)",
            re.I,
        ),
        re.compile(
            r"email\s+(?P<to>.+?)\s+about\s+(?P<subject>.+)",
            re.I,
        ),
    ]

    for pattern in patterns:
        match = pattern.search(user_input)
        if match:
            to = match.group("to").strip()
            subject = match.group("subject").strip()
            body = subject
            return to, subject, body

    return "unknown@example.com", "Follow up", user_input.strip()


def _extract_event_fields(user_input: str) -> tuple[str, str, str]:
    text = user_input.strip()
    when = "unspecified time"
    attendees = ""

    when_match = re.search(r"(today|tomorrow|friday|monday|tuesday|wednesday|thursday|saturday|sunday|\d{1,2}(?::\d{2})?\s?(?:am|pm))", text, re.I)
    if when_match:
        when = when_match.group(1)

    title_match = re.search(r"(?:schedule|create|book|set up)\s+(.+?)(?:\s+for\s+|\s+at\s+|$)", text, re.I)
    title = title_match.group(1).strip() if title_match else "New meeting"

    attendee_match = re.search(r"with\s+(.+)", text, re.I)
    if attendee_match:
        attendees = attendee_match.group(1).strip()

    return title, when, attendees


def _workflow_from_text(user_input: str) -> dict[str, Any]:
    text = " ".join(user_input.split())
    lowered = text.lower()

    trigger = "manual"
    if "email" in lowered or "gmail" in lowered:
        trigger = "gmail"
    elif "calendar" in lowered or "meeting" in lowered:
        trigger = "calendar"

    condition = "always"
    if "today" in lowered:
        condition = "today"
    elif "unread" in lowered:
        condition = "unread"

    action = "notify me"
    if "summarize" in lowered:
        action = "summarize"
    elif "send" in lowered:
        action = "send email"
    elif "schedule" in lowered:
        action = "create event"

    name = f"workflow-{uuid.uuid4().hex[:8]}"
    return save_workflow(name=name, trigger=trigger, condition=condition, action=action)


def _execute_status_check(user_input: str) -> dict[str, Any]:
    lowered = user_input.lower()

    if any(token in lowered for token in ["email", "emails", "gmail", "mail"]):
        query = _gmail_query_for_text(user_input)
        tool_output = gmail_read(query)
        return {
            "route": "status_check",
            "action_taken": "Read email status",
            "pending_approvals": [],
            "tool_outputs": [tool_output],
            "summary": (
                f"FlowDesk classified this as a read-only Gmail request and built the query `{query}`. "
                "No approval is needed for read access. Gmail is still a stub in this repo, so live messages were not fetched."
            ),
        }

    if any(token in lowered for token in ["calendar", "meeting", "schedule"]):
        date_range = _calendar_range_for_text(user_input)
        tool_output = calendar_read(date_range)
        return {
            "route": "status_check",
            "action_taken": "Read calendar status",
            "pending_approvals": [],
            "tool_outputs": [tool_output],
            "summary": (
                f"FlowDesk classified this as a read-only calendar request for `{date_range}`. "
                "No approval is needed for read access. Calendar is still a stub in this repo, so no live events were fetched."
            ),
        }

    return {
        "route": "status_check",
        "action_taken": "Reviewed request",
        "pending_approvals": [],
        "tool_outputs": [],
        "summary": "FlowDesk treated this as a read-only status check, but no matching Gmail or Calendar action was inferred.",
    }


def _execute_one_time_task(user_input: str) -> dict[str, Any]:
    lowered = user_input.lower()

    if any(token in lowered for token in ["send", "reply", "draft", "email"]) and any(
        token in lowered for token in ["to ", "email", "gmail", "mail"]
    ):
        to, subject, body = _extract_email_fields(user_input)
        approval = gmail_send(to=to, subject=subject, body=body)
        return {
            "route": "one_time_task",
            "action_taken": "Prepared email draft",
            "pending_approvals": [approval],
            "tool_outputs": [],
            "summary": "FlowDesk prepared an email draft and queued it for approval before sending.",
        }

    if any(token in lowered for token in ["schedule", "book", "create", "invite"]) and any(
        token in lowered for token in ["meeting", "calendar", "event"]
    ):
        title, when, attendees = _extract_event_fields(user_input)
        approval = calendar_create(title=title, when=when, attendees=attendees)
        return {
            "route": "one_time_task",
            "action_taken": "Prepared calendar event",
            "pending_approvals": [approval],
            "tool_outputs": [],
            "summary": "FlowDesk prepared a calendar event and queued it for approval before creating it.",
        }

    return _execute_status_check(user_input)


def run_flowdesk(user_input: str) -> dict[str, Any]:
    """Deterministic control plane for FlowDesk.

    The original concept is a voice-first workflow assistant with intent routing,
    read-only actions executed directly, and write actions staged behind approvals.
    This function keeps that behavior stable even when the LLM output is verbose.
    """

    route = route_request(user_input)

    if route == "create_workflow":
        workflow = _workflow_from_text(user_input)
        return {
            "route": route,
            "action_taken": "Saved workflow definition",
            "pending_approvals": [],
            "tool_outputs": [workflow],
            "workflow": workflow,
            "summary": (
                "FlowDesk classified this as a reusable workflow request and converted it into a saved workflow definition."
            ),
            "llm": {
                "base_url": FLOWDESK_LLM_BASE_URL,
                "model": FLOWDESK_LLM_MODEL,
                "api_key_configured": bool(FLOWDESK_LLM_API_KEY),
            },
        }

    result = _execute_status_check(user_input) if route == "status_check" else _execute_one_time_task(user_input)
    result["llm"] = {
        "base_url": FLOWDESK_LLM_BASE_URL,
        "model": FLOWDESK_LLM_MODEL,
        "api_key_configured": bool(FLOWDESK_LLM_API_KEY),
    }
    result["connections"] = [
        get_gmail_connection_status(),
        get_google_calendar_connection_status(),
    ]
    return result
