from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agents.crew import run_flowdesk
import uuid, json
from datetime import datetime

app = FastAPI(title="FlowDesk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory approval queue (swap with Supabase in prod)
approval_queue: dict = {}
workflows: list = []

# ── SCHEMAS ──────────────────────────────────────────────────────────────────

class UserRequest(BaseModel):
    text: str  # voice transcript or typed input

class ApprovalAction(BaseModel):
    action: str  # "approve" | "reject" | "edit"
    edited_payload: dict | None = None

# ── ROUTES ───────────────────────────────────────────────────────────────────

@app.post("/ask")
async def ask(req: UserRequest):
    """Main endpoint — processes voice/text input through CrewAI."""
    result = run_flowdesk(req.text)

    # Parse pending approvals from agent output
    pending = extract_pending_approvals(result["result"])
    for item in pending:
        aid = str(uuid.uuid4())[:8]
        approval_queue[aid] = {
            "id": aid,
            "payload": item,
            "status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }

    return {
        "summary": result["result"],
        "pending_approvals": list(approval_queue.values()),
        "workflows": workflows,
    }

@app.get("/approvals")
async def get_approvals():
    return {"approvals": [v for v in approval_queue.values() if v["status"] == "pending"]}

@app.post("/approvals/{approval_id}")
async def handle_approval(approval_id: str, action: ApprovalAction):
    if approval_id not in approval_queue:
        raise HTTPException(status_code=404, detail="Approval not found")

    item = approval_queue[approval_id]
    if action.action == "approve":
        item["status"] = "approved"
        # TODO: trigger actual execution (Gmail send, Calendar create, etc.)
        return {"message": "Executed", "item": item}
    elif action.action == "reject":
        item["status"] = "rejected"
        return {"message": "Rejected"}
    elif action.action == "edit":
        item["payload"] = action.edited_payload
        item["status"] = "approved"
        return {"message": "Edited and executed", "item": item}

@app.get("/workflows")
async def get_workflows():
    return {"workflows": workflows}

@app.delete("/workflows/{workflow_id}")
async def delete_workflow(workflow_id: str):
    global workflows
    workflows = [w for w in workflows if w["id"] != workflow_id]
    return {"message": "Deleted"}

# ── HELPERS ──────────────────────────────────────────────────────────────────

def extract_pending_approvals(agent_output: str) -> list:
    """Parse PENDING_APPROVAL tags from agent output."""
    import re
    items = re.findall(r"\[PENDING_APPROVAL\](.*?)(?=\[|$)", agent_output)
    return [{"raw": item.strip()} for item in items]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
