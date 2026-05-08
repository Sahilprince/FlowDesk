import json
import os
import secrets
import uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import RedirectResponse

from crew import run_flowdesk
from integrations import (
    get_github_connection_status,
    get_gmail_connection_status,
    get_google_calendar_connection_status,
)

app = FastAPI(title="FlowDesk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory stores. Replace with a real database in production.
approval_queue: dict[str, dict] = {}
workflows: list[dict] = []
oauth_states: dict[str, dict] = {}
ENV_FILE = Path(".env")


def _frontend_url() -> str:
    return os.getenv("FLOWDESK_APP_URL", "http://localhost:5173")


def _read_env_lines() -> list[str]:
    if ENV_FILE.exists():
        return ENV_FILE.read_text(encoding="utf-8").splitlines()
    return []


def persist_env_var(key: str, value: str) -> None:
    lines = _read_env_lines()
    updated = False
    new_lines = []

    for line in lines:
        if line.startswith(f"{key}="):
            new_lines.append(f"{key}={value}")
            updated = True
        else:
            new_lines.append(line)

    if not updated:
        new_lines.append(f"{key}={value}")

    ENV_FILE.write_text("\n".join(new_lines).strip() + "\n", encoding="utf-8")
    os.environ[key] = value


def persist_env_vars(values: dict[str, str]) -> None:
    for key, value in values.items():
        persist_env_var(key, value)


def _encode_state(payload: dict) -> str:
    raw = json.dumps(payload).encode("utf-8")
    return urlsafe_b64encode(raw).decode("utf-8")


def _decode_state(value: str) -> dict:
    raw = urlsafe_b64decode(value.encode("utf-8"))
    return json.loads(raw.decode("utf-8"))


def _post_form(url: str, data: dict[str, str], headers: dict[str, str] | None = None) -> dict:
    encoded = urlencode(data).encode("utf-8")
    request = Request(url, data=encoded, headers=headers or {}, method="POST")
    with urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))


def _google_scopes_for_service(service: str) -> list[str]:
    if service == "gmail":
        return [
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/gmail.send",
        ]
    if service == "google_calendar":
        return [
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events",
        ]
    raise HTTPException(status_code=400, detail="Unsupported Google service")


def get_connection_catalog() -> list[dict]:
    return [
        get_gmail_connection_status(),
        get_google_calendar_connection_status(),
        get_github_connection_status(),
        {
            "service": "slack",
            "label": "Slack",
            "state": "planned",
            "auth_type": "oauth",
            "configured": False,
            "token_present": False,
            "connectable": False,
            "next_step": "Add a Slack adapter and bot token wiring.",
        },
        {
            "service": "notion",
            "label": "Notion",
            "state": "planned",
            "auth_type": "oauth",
            "configured": False,
            "token_present": False,
            "connectable": False,
            "next_step": "Add a Notion adapter and integration token wiring.",
        },
    ]


class UserRequest(BaseModel):
    text: str


class ApprovalAction(BaseModel):
    action: str  # approve | reject | edit
    edited_payload: dict | None = None


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "connections": get_connection_catalog(),
    }


@app.post("/ask")
async def ask(req: UserRequest) -> dict:
    result = run_flowdesk(req.text)

    new_approvals = []
    for item in result.get("pending_approvals", []):
        aid = str(uuid.uuid4())[:8]
        approval = {
            "id": aid,
            "payload": item,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        approval_queue[aid] = approval
        new_approvals.append(approval)

    workflow = result.get("workflow")
    if workflow:
        saved = {
            "id": workflow.get("name", str(uuid.uuid4())[:8]),
            "name": workflow.get("name"),
            "trigger": workflow.get("trigger"),
            "condition": workflow.get("condition"),
            "action": workflow.get("action"),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        workflows.append(saved)

    return {
        "route": result.get("route"),
        "action_taken": result.get("action_taken"),
        "summary": result.get("summary"),
        "pending_approvals": [v for v in approval_queue.values() if v["status"] == "pending"],
        "new_pending_approvals": new_approvals,
        "workflows": workflows,
        "tool_outputs": result.get("tool_outputs", []),
        "llm": result.get("llm", {}),
        "connections": result.get("connections", get_connection_catalog()),
    }


@app.get("/connections")
async def get_connections() -> dict:
    return {"connections": get_connection_catalog()}


@app.get("/connections/{service}/authorize")
async def authorize_connection(service: str, return_to: str | None = None) -> RedirectResponse:
    target = return_to or _frontend_url()
    state_id = secrets.token_urlsafe(24)
    oauth_states[state_id] = {"service": service, "return_to": target}

    if service in {"gmail", "google_calendar"}:
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
        if not client_id or not redirect_uri:
            raise HTTPException(status_code=400, detail="Google OAuth is not configured on the server.")

        scopes = _google_scopes_for_service(service)
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
            "scope": " ".join(scopes),
            "state": _encode_state({"id": state_id, "service": service}),
        }
        return RedirectResponse(
            url=f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}",
            status_code=307,
        )

    if service == "github":
        client_id = os.getenv("GITHUB_CLIENT_ID")
        redirect_uri = os.getenv("GITHUB_REDIRECT_URI")
        if not client_id or not redirect_uri:
            raise HTTPException(status_code=400, detail="GitHub OAuth is not configured on the server.")

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": "repo read:user user:email",
            "state": _encode_state({"id": state_id, "service": service}),
        }
        return RedirectResponse(
            url=f"https://github.com/login/oauth/authorize?{urlencode(params)}",
            status_code=307,
        )

    raise HTTPException(status_code=404, detail="Connection flow not available for this service.")


@app.get("/oauth/google/callback")
async def google_oauth_callback(code: str, state: str, scope: str | None = None) -> RedirectResponse:
    decoded = _decode_state(state)
    state_id = decoded.get("id")
    service = decoded.get("service")
    pending = oauth_states.pop(state_id, None)
    if not pending or service not in {"gmail", "google_calendar"}:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    token_data = _post_form(
        "https://oauth2.googleapis.com/token",
        {
            "code": code,
            "client_id": os.getenv("GOOGLE_CLIENT_ID", ""),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET", ""),
            "redirect_uri": os.getenv("GOOGLE_REDIRECT_URI", ""),
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    refresh_token = token_data.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Google OAuth did not return a refresh token.")

    persist_env_vars(
        {
            "GOOGLE_GMAIL_REFRESH_TOKEN": refresh_token,
            "GOOGLE_CALENDAR_REFRESH_TOKEN": refresh_token,
        }
    )

    redirect_to = f"{pending['return_to']}?connected={service}"
    if scope:
        redirect_to += "&scope_granted=1"
    return RedirectResponse(url=redirect_to, status_code=303)


@app.get("/oauth/github/callback")
async def github_oauth_callback(code: str, state: str) -> RedirectResponse:
    decoded = _decode_state(state)
    state_id = decoded.get("id")
    service = decoded.get("service")
    pending = oauth_states.pop(state_id, None)
    if not pending or service != "github":
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state.")

    token_data = _post_form(
        "https://github.com/login/oauth/access_token",
        {
            "code": code,
            "client_id": os.getenv("GITHUB_CLIENT_ID", ""),
            "client_secret": os.getenv("GITHUB_CLIENT_SECRET", ""),
            "redirect_uri": os.getenv("GITHUB_REDIRECT_URI", ""),
        },
        headers={"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"},
    )

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="GitHub OAuth did not return an access token.")

    persist_env_var("GITHUB_ACCESS_TOKEN", access_token)
    return RedirectResponse(url=f"{pending['return_to']}?connected=github", status_code=303)


@app.get("/approvals")
async def get_approvals() -> dict:
    return {"approvals": [v for v in approval_queue.values() if v["status"] == "pending"]}


@app.post("/approvals/{approval_id}")
async def handle_approval(approval_id: str, action: ApprovalAction) -> dict:
    if approval_id not in approval_queue:
        raise HTTPException(status_code=404, detail="Approval not found")

    item = approval_queue[approval_id]
    payload = action.edited_payload or item["payload"]

    if action.action == "approve":
        item["status"] = "approved"
        item["executed_at"] = datetime.now(timezone.utc).isoformat()
        return {
            "message": "Approved and executed",
            "item": item,
            "execution_result": _simulate_execution(payload),
        }

    if action.action == "reject":
        item["status"] = "rejected"
        item["rejected_at"] = datetime.now(timezone.utc).isoformat()
        return {"message": "Rejected", "item": item}

    if action.action == "edit":
        item["payload"] = payload
        item["status"] = "approved"
        item["executed_at"] = datetime.now(timezone.utc).isoformat()
        return {
            "message": "Edited, approved, and executed",
            "item": item,
            "execution_result": _simulate_execution(payload),
        }

    raise HTTPException(status_code=400, detail="Invalid action")


@app.get("/workflows")
async def get_workflows() -> dict:
    return {"workflows": workflows}


@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str) -> dict:
    global workflows
    workflows = [w for w in workflows if w["id"] != workflow_id]
    return {"message": "Deleted"}


def _simulate_execution(payload: dict) -> dict:
    tool_name = payload.get("tool")

    if tool_name == "gmail_send":
        return {
            "tool": tool_name,
            "status": "stub",
            "message": f"Would send email to {payload.get('to')!r} with subject {payload.get('subject')!r}.",
        }
    if tool_name == "calendar_create":
        return {
            "tool": tool_name,
            "status": "stub",
            "message": f"Would create event {payload.get('title')!r} at {payload.get('when')!r}.",
        }
    return {"tool": tool_name or "unknown", "status": "stub", "message": "No live integration is configured yet."}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
