"""modal_vlm.py - the engine's own GPU fallback for A1 / A5 on Modal (modal.com): vLLM's OpenAI-compatible server
running Qwen3-VL-30B-A3B-Instruct (FP8: about 31 GB of weights, 3B parameters active per token, so it writes fast)
on one L40S. Billed per second from Modal's monthly credit; it sleeps when idle.

One-time setup, on the PC (any Python 3.10+ environment):
    pip install modal
    modal setup                                          # log in (opens the browser)
    modal secret create cosmogon-vllm VLLM_API_KEY=<a long random token you make up>
    modal deploy deploy/modal_vlm.py                     # prints https://<workspace>--cosmogon-vlm-serve.modal.run

Then add two lines to worker/.env on the PC and on the server (never paste the token in chat):
    MODAL_BASE=https://<workspace>--cosmogon-vlm-serve.modal.run
    MODAL_API_KEY=<the same token>
and restart the worker. Optional: MODAL_WARM=off (default "job": the worker boots the GPU when a job starts and keeps
it up until the job ends, so A1 / A5 never wait for a cold start; this spends GPU time on every job, used or not).
Check it: curl https://<...>.modal.run/health  (the first call after idle boots it: 2-4 min; the very first deploy
also downloads the weights once into the cosmogon-hf-cache Volume).

Cost (Modal Starter plan, read 2026-11-22): $0/month with $30 of compute credit each month; L40S about $1.95/h,
billed per second, plus a little CPU/memory. A job kept warm end to end is roughly 10-15 GPU-minutes (~$0.35-0.50).
"""
import json
import os
import subprocess

import modal

MODEL = os.environ.get("MODAL_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8")
GPU = os.environ.get("MODAL_GPU", "L40S")              # A100-80GB / H100 also work (faster, dearer per second)

image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("vllm==0.11.0", "huggingface_hub[hf_transfer]")   # Qwen3-VL needs vLLM >= 0.11
         .env({"HF_HUB_ENABLE_HF_TRANSFER": "1"}))
hf_cache = modal.Volume.from_name("cosmogon-hf-cache", create_if_missing=True)      # weights: downloaded once
vllm_cache = modal.Volume.from_name("cosmogon-vllm-cache", create_if_missing=True)  # compiled kernels: faster boots
app = modal.App("cosmogon-vlm")


@app.function(image=image, gpu=GPU,
              volumes={"/root/.cache/huggingface": hf_cache, "/root/.cache/vllm": vllm_cache},
              secrets=[modal.Secret.from_name("cosmogon-vllm")],
              scaledown_window=180,          # sleep 3 min after the last request (the worker pings once a minute)
              timeout=60 * 60)
@modal.concurrent(max_inputs=8)
@modal.web_server(port=8000, startup_timeout=20 * 60)
def serve():
    subprocess.Popen([
        "vllm", "serve", MODEL, "--host", "0.0.0.0", "--port", "8000", "--served-model-name", MODEL,
        "--api-key", os.environ["VLLM_API_KEY"],        # /v1/* needs it; /health stays open (the worker's warm-up)
        "--max-model-len", "65536",                     # A1: 5 images + brief + 9K out; A5: spec + 20K out
        "--limit-mm-per-prompt", json.dumps({"image": 6}),
        "--gpu-memory-utilization", "0.92", "--max-num-seqs", "4"])
