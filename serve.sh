#!/bin/bash
set -euo pipefail

# AMD MI300X optimized vLLM server.
# Override with env vars when needed.

export HIP_VISIBLE_DEVICES="${HIP_VISIBLE_DEVICES:-0}"
export PYTORCH_ROCM_ARCH="${PYTORCH_ROCM_ARCH:-gfx942}"
export VLLM_USE_ROCM=1

MODEL_ID="${FLOWDESK_LLM_MODEL:-deepseek-ai/DeepSeek-R1-Distill-Llama-8B}"
PORT="${FLOWDESK_LLM_PORT:-8000}"
GPU_MEMORY_UTILIZATION="${FLOWDESK_GPU_MEMORY_UTILIZATION:-0.85}"
MAX_MODEL_LEN="${FLOWDESK_MAX_MODEL_LEN:-8192}"

python3 -m vllm.entrypoints.openai.api_server \
  --model "${MODEL_ID}" \
  --tokenizer "${MODEL_ID}" \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --dtype float16 \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json \
  --trust-remote-code
