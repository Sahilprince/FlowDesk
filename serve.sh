#!/bin/bash
# AMD MI300X optimized vLLM server
# Requires: pip install vllm (ROCm build)

export HIP_VISIBLE_DEVICES=0
export PYTORCH_ROCM_ARCH="gfx942"  # MI300X arch
export VLLM_USE_ROCM=1

# Start vLLM with OpenAI-compatible API
python -m vllm.entrypoints.openai.api_server \
  --model "deepseek-ai/DeepSeek-R1-Distill-Llama-8B" \
  --tokenizer "deepseek-ai/DeepSeek-R1-Distill-Llama-8B" \
  --host 0.0.0.0 \
  --port 8000 \
  --dtype float16 \
  --max-model-len 8192 \
  --gpu-memory-utilization 0.85 \
  --tensor-parallel-size 1 \
  --enable-auto-tool-choice \
  --tool-call-parser llama3_json \
  --trust-remote-code
