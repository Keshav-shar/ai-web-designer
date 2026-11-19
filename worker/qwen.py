"""qwen.py - minimal OpenAI-compatible chat client for a hosted Qwen endpoint.

Env (never written to files): QWEN_API_KEY, QWEN_BASE (e.g. https://dashscope-intl.aliyuncs.com/compatible-mode/v1
or https://openrouter.ai/api/v1), QWEN_MODEL (coder-class model for sections), QWEN_SPLIT_MODEL (optional, a
small fast model for the split; defaults to QWEN_MODEL), QWEN_VL_MODEL (optional vision model for layout notes).
"""
from __future__ import annotations

import base64
import json
import os
import random
import re
import time
from pathlib import Path

import httpx


class QwenError(RuntimeError):
    pass


class Qwen:
    def __init__(self):
        self.key = os.getenv("QWEN_API_KEY", "").strip()
        self.base = os.getenv("QWEN_BASE", "").strip().rstrip("/")
        self.model = os.getenv("QWEN_MODEL", "").strip()
        self.split_model = os.getenv("QWEN_SPLIT_MODEL", "").strip() or self.model
        self.vl_model = os.getenv("QWEN_VL_MODEL", "").strip()
        self.http = httpx.Client(timeout=httpx.Timeout(180, connect=15))

    @property
    def ok(self) -> bool:
        return bool(self.key and self.base and self.model)

    def chat(self, messages, *, model=None, json_mode=False, max_tokens=4096, temperature=0.6, tries=4) -> str:
        if not self.ok:
            raise QwenError("Qwen is not configured (QWEN_API_KEY, QWEN_BASE, QWEN_MODEL)")
        body = {"model": model or self.model, "messages": messages, "max_tokens": max_tokens,
                "temperature": temperature}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        last = None
        for i in range(tries):
            try:
                r = self.http.post(f"{self.base}/chat/completions", json=body,
                                   headers={"Authorization": f"Bearer {self.key}"})
            except httpx.HTTPError as e:
                last = f"{type(e).__name__}: {e}"
            else:
                if r.status_code == 200:
                    msg = r.json()["choices"][0]["message"]["content"] or ""
                    return re.sub(r"<think>.*?</think>", "", msg, flags=re.S).strip()   # drop reasoning blocks
                last = f"HTTP {r.status_code}: {r.text[:300]}"
                if r.status_code not in (408, 409, 429, 500, 502, 503, 504):
                    break
                ra = r.headers.get("retry-after")
                if ra and ra.isdigit():
                    time.sleep(min(60, int(ra)))
                    continue
            time.sleep(min(30, 2 ** i + random.random()))
        raise QwenError(last or "request failed")

    def chat_json(self, messages, **kw) -> dict:
        text = self.chat(messages, json_mode=True, **kw)
        m = re.search(r"\{.*\}", text, re.S)
        if not m:
            raise QwenError(f"no JSON object in reply: {text[:200]!r}")
        return json.loads(m.group(0))

    def describe_layout(self, image: Path) -> str | None:
        """Optional: a vision model turns the layout reference into a structural note (no copy, no colours)."""
        if not (self.ok and self.vl_model):
            return None
        data = base64.b64encode(image.read_bytes()).decode()
        mime = "image/webp" if image.suffix == ".webp" else "image/jpeg"
        return self.chat([{"role": "user", "content": [
            {"type": "text", "text": "Describe only the STRUCTURE of this website screenshot for a developer who "
                                     "will build a different site with the same skeleton: hero arrangement "
                                     "(split / centred / full-bleed), grid columns, card shapes, spacing rhythm, "
                                     "nav style, image placement, alignment. Ignore its text, brand and colours. "
                                     "8 short bullet points."},
            {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}]}],
            model=self.vl_model, max_tokens=500, temperature=0.2)
