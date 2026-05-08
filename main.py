import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from crew import run_flowdesk
from integrations import get_gmail_connection_status, get_google_calendar_connection_status

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


def get_connection_catalog() -> list[dict]:
    return [
        get_gmail_connection_status(),
        get_google_calendar_connection_status(),
        {
            "service": "slack",
            "label": "Slack",
            "state": "planned",
            "auth_type": "oauth",
            "configured": False,
            "token_present": False,
            "next_step": "Add a Slack adapter and bot token wiring.",
        },
        {
            "service": "notion",
            "label": "Notion",
            "state": "planned",
            "auth_type": "oauth",
            "configured": False,
            "token_present": False,
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
