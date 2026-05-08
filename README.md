# FlowDesk

FlowDesk is a voice-first workflow assistant for personal ops tasks like reading email, staging outgoing messages, checking calendars, and saving reusable automations.

## Concept

The core control flow is:

```text
Voice/Text -> Intent Router -> Status Check | One-Time Task | Workflow Save
                               |                  |
                               |                  -> Approval Gate for write actions
                               |
                               -> Direct execution for read-only actions
```

Two rules matter:

1. Read-only actions should execute immediately with no approval step.
2. Write actions like sending email or creating calendar events must be staged for approval.

The original repo depended on free-form LLM output for this control flow. That caused unstable behavior. The current version keeps the routing deterministic and uses the LLM server as supporting infrastructure rather than as the source of truth for approvals.

## Current State

- Backend is runnable from the repo root.
- Frontend is scaffolded with Vite from the repo root.
- Gmail and Calendar are still stub tools. You need to replace them with real Gmail or calendar integrations to get live data.
- AMD MI300X / ROCm vLLM settings are aligned around `http://localhost:8000/v1`.

## Files

- [crew.py](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/crew.py): Intent routing and task execution logic
- [main.py](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/main.py): FastAPI API and approval queue
- [integrations/gmail.py](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/integrations/gmail.py): Gmail adapter and connection status
- [integrations/google_calendar.py](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/integrations/google_calendar.py): Calendar adapter and connection status
- [App.jsx](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/App.jsx): React UI
- [main.jsx](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/main.jsx): React entrypoint
- [serve.sh](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/serve.sh): AMD/vLLM server launcher

## Setup On Your AMD GPU Droplet

### 1. Python environment

```bash
python3 -m venv flowenv
source flowenv/bin/activate
pip install -U pip
pip install -r requirements.txt
```

### 2. Install ROCm vLLM

```bash
pip install vllm --extra-index-url https://download.pytorch.org/whl/rocm6.1
```

### 3. Start the model server

```bash
chmod +x serve.sh
./serve.sh
```

This serves an OpenAI-compatible API on `http://localhost:8000/v1`.

### 4. Start the backend

```bash
python3 main.py
```

The backend listens on `http://0.0.0.0:8080`.

### 5. Start the frontend

```bash
npm install
npm run dev
```

The UI listens on `http://0.0.0.0:5173`.

## Test The Backend

Read-only request:

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"text": "summarize my emails from today"}'
```

Expected behavior now:

- `route` should be `status_check`
- `pending_approvals` should be empty
- `summary` should explain that FlowDesk built a Gmail read query and that Gmail is still stubbed

Write request:

```bash
curl -X POST http://localhost:8080/ask \
  -H "Content-Type: application/json" \
  -d '{"text": "send Alex an email about the roadmap update"}'
```

Expected behavior:

- `route` should be `one_time_task`
- `pending_approvals` should contain a `gmail_send` payload

## Environment Variables

Optional overrides:

```bash
export FLOWDESK_LLM_MODEL=deepseek-ai/DeepSeek-R1-Distill-Llama-8B
export FLOWDESK_LLM_BASE_URL=http://localhost:8000/v1
export FLOWDESK_LLM_API_KEY=unused
export FLOWDESK_LLM_PORT=8000
```

Google connection scaffolding:

```bash
export GOOGLE_CLIENT_ID=your-google-client-id
export GOOGLE_CLIENT_SECRET=your-google-client-secret
export GOOGLE_REDIRECT_URI=http://localhost:8080/oauth/google/callback
export GOOGLE_GMAIL_REFRESH_TOKEN=replace-after-oauth
export GOOGLE_CALENDAR_REFRESH_TOKEN=replace-after-oauth
```

## Integration Architecture

Service integrations now live in adapter files instead of being hardcoded into the UI or route handlers.

- `integrations/gmail.py`
  - expose Gmail connection status
  - implement Gmail read and send calls
- `integrations/google_calendar.py`
  - expose Calendar connection status
  - implement Calendar read and create calls
- `crew.py`
  - call adapter functions
  - keep intent routing and approval behavior
- `main.py`
  - expose `/connections`
  - return connection state to the UI
- `App.jsx`
  - show a Connections panel
  - keep approvals and workflows visible beside chat

The next production step is to add real Google OAuth start/callback endpoints and exchange the authorization code for refresh tokens.

## Next Step To Make It Real

Replace the stub tools in [crew.py](/mnt/d/Coding/Projects/AgenticAI/FlowDesk/crew.py) with real integrations:

- `gmail_read`
- `gmail_send`
- `calendar_read`
- `calendar_create`

That is the missing piece between a demo control plane and a functioning assistant.
