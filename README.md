# FlowDesk ⚡
> Voice-first AI workflow assistant powered by DeepSeek + CrewAI on AMD MI300X

## Architecture
```
Voice → Intent Router → Task Agent ──→ Gmail / Calendar
                     → Workflow Agent → Saved Workflows
                     ↓
              Approval Gate UI → Execute
```

## Stack
- **LLM**: DeepSeek-R1-Distill-Llama-8B via vLLM (ROCm)
- **Agents**: CrewAI (multi-agent orchestration)
- **Compute**: AMD MI300X / ROCm on AMD Developer Cloud
- **Backend**: FastAPI
- **Frontend**: React + Web Speech API

---

## Setup on AMD Developer Cloud

### 1. Install ROCm vLLM
```bash
pip install vllm --extra-index-url https://download.pytorch.org/whl/rocm6.1
```

### 2. Start LLM Server (MI300X optimized)
```bash
chmod +x backend/serve.sh
./backend/serve.sh
# Model auto-downloads from HuggingFace (~16GB)
```

### 3. Start Backend
```bash
cd backend
pip install -r requirements.txt
python api/main.py
```

### 4. Start Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## Key Files
```
backend/
  serve.sh          # vLLM server (MI300X optimized)
  agents/crew.py    # CrewAI agents (Router, Task, Workflow)
  api/main.py       # FastAPI + approval queue
frontend/
  src/App.jsx       # React UI + voice + approval cards
```

## AMD MI300X Optimizations
- `PYTORCH_ROCM_ARCH=gfx942` targets MI300X specifically
- `float16` dtype for max throughput
- `gpu-memory-utilization=0.85` — safe ceiling for 192GB HBM3
- `tensor-parallel-size=1` — single GPU sufficient for 8B model

## Extending
- Wire real Gmail/Calendar: replace stub tools in `agents/crew.py` with MCP calls
- Add Supabase: swap `approval_queue` dict with Supabase client
- Add more agents: Slack, Notion, Linear — each is one new `@tool` function
