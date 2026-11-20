"""providers.py - the two free-tier providers, over plain httpx (no SDKs).

Gemini (Google AI Studio, generateContent v1beta): multimodal parts, responseJsonSchema, per-part media resolution
(falls back to the global setting if the API rejects it), thinking level per call (low by default; the composer and the director think more).
Groq (OpenAI-compatible): strict json_schema (constrained decoding), reasoning kept low/off and hidden, images as
data URLs (Qwen 3.8: at most 3 images, 2048 tokens each), rate-limit headers fed to budget.Buckets.

Errors are mapped to ProviderError.kind, which the router acts on:
  quota_day  daily quota gone -> mark the model exhausted in the ledger, use the next one
  rate       per-minute limit -> wait (short) or use the next model
  too_large  the request exceeds the model's minute window -> next model
  truncated  the reply hit its token cap -> retry once bigger, else next model
  bad_request / auth / server / network / blocked
Keys are passed per call by the pipeline (keys.Ring: several per provider, failover on limits); never logged.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import budget, schemas as sc

GEMINI_BASE = os.getenv("GEMINI_BASE", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
GROQ_BASE = os.getenv("GROQ_BASE", "https://api.groq.com/openai/v1").rstrip("/")
RES_LEVEL = {"low": "MEDIA_RESOLUTION_LOW", "medium": "MEDIA_RESOLUTION_MEDIUM", "high": "MEDIA_RESOLUTION_HIGH"}


class ProviderError(RuntimeError):
    def __init__(self, kind: str, msg: str, retry_after: float = 0.0):
        super().__init__(f"{kind}: {msg}")
        self.kind, self.retry_after = kind, retry_after


@dataclass
class Reply:
    text: str
    model: str
    finish: str
    usage: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)
    ms: int = 0

    def json(self) -> dict:
        t = re.sub(r"<think>.*?</think>", "", self.text, flags=re.S).strip()
        t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
        try:
            return json.loads(t)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", t, re.S)
            if not m:
                raise ProviderError("bad_output", f"no JSON object in reply ({t[:120]!r})") from None
            return json.loads(m.group(0))


def jpeg_b64(path: str | Path, side: int) -> str:
    from PIL import Image
    with Image.open(path) as im:
        im.seek(0)
        im = im.convert("RGB")
        im.thumbnail((side, side))
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def composite_b64(labelled: list[tuple[str, str]], cell: int = 512) -> str:
    """Several labelled images on one sheet (for providers that allow few images, e.g. Qwen's 3 at 2048 tokens)."""
    from PIL import Image, ImageDraw
    cols = 3 if len(labelled) > 4 else 2
    rows = -(-len(labelled) // cols)
    sheet = Image.new("RGB", (cols * cell, rows * cell), (245, 245, 245))
    draw = ImageDraw.Draw(sheet)
    for i, (label, path) in enumerate(labelled):
        with Image.open(path) as im:
            im.seek(0)
            im = im.convert("RGB")
            im.thumbnail((cell - 8, cell - 30))
            x, y = (i % cols) * cell, (i // cols) * cell
            sheet.paste(im, (x + (cell - im.width) // 2, y + 26))
            draw.rectangle((x, y, x + cell, y + 22), fill=(20, 20, 20))
            draw.text((x + 6, y + 5), label, fill=(255, 255, 255))
    buf = io.BytesIO()
    sheet.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _http() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(240, connect=15))


# --------------------------------------------------------------------------- Gemini
class Gemini:
    per_part_res = True                       # flipped off for the process if the API rejects per-part resolution
    thinking = True

    def __init__(self):
        self.http = _http()
        self._models: list[str] | None = None

    def models(self, key: str) -> list[str]:
        if self._models is None:
            r = self.http.get(f"{GEMINI_BASE}/models", params={"pageSize": 200}, headers={"x-goog-api-key": key})
            if r.status_code != 200:
                raise ProviderError("auth" if r.status_code in (401, 403) else "server", f"list models HTTP {r.status_code}")
            self._models = [m["name"].split("/", 1)[-1] for m in r.json().get("models", [])
                            if "generateContent" in m.get("supportedGenerationMethods", [])]
        return self._models

    def _parts(self, parts: list[dict]) -> list[dict]:
        out = []
        for p in parts:
            if "text" in p:
                out.append({"text": p["text"]})
            else:
                part = {"inlineData": {"mimeType": "image/jpeg", "data": jpeg_b64(p["image"], 1536)}}
                if self.per_part_res:
                    part["mediaResolution"] = {"level": RES_LEVEL.get(p.get("res", "high"), "MEDIA_RESOLUTION_HIGH")}
                out.append(part)
        return out

    def generate(self, model: str, system: str, parts: list[dict], *, key: str, schema: dict | None = None,
                 max_out: int = 4096, temperature: float = 0.2, timeout: float = 120.0,
                 thinking: str = "low") -> Reply:
        if not key:
            raise ProviderError("auth", "no Gemini key")
        overloads = 0
        for attempt in range(8):
            cfg = {"temperature": temperature, "maxOutputTokens": max_out}
            if schema is not None:
                cfg.update(responseMimeType="application/json", responseJsonSchema=sc.inline_refs(sc.provider_schema(schema)))
            if self.thinking:
                cfg["thinkingConfig"] = {"thinkingLevel": thinking}
            if not self.per_part_res and any("image" in p for p in parts):
                cfg["mediaResolution"] = "MEDIA_RESOLUTION_HIGH"
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": self._parts(parts)}], "generationConfig": cfg}
            t0 = time.time()
            try:
                r = self.http.post(f"{GEMINI_BASE}/models/{model}:generateContent", json=body,
                                   headers={"x-goog-api-key": key}, timeout=httpx.Timeout(timeout, connect=15))
            except httpx.TimeoutException as e:            # a slow model: don't wait another full timeout here
                raise ProviderError("timeout", f"no reply within {timeout:.0f}s ({type(e).__name__})") from None
            except httpx.HTTPError as e:
                if attempt < 1:
                    time.sleep(2)
                    continue
                raise ProviderError("network", f"{type(e).__name__}: {e}") from None
            ms = int((time.time() - t0) * 1000)
            if r.status_code == 200:
                d = r.json()
                cand = (d.get("candidates") or [{}])[0]
                finish = cand.get("finishReason", "")
                text = "".join(p.get("text", "") for p in (cand.get("content") or {}).get("parts", []) if not p.get("thought"))
                u = d.get("usageMetadata", {})
                usage = {"in": u.get("promptTokenCount", 0), "out": u.get("candidatesTokenCount", 0),
                         "thinking": u.get("thoughtsTokenCount", 0), "cached": u.get("cachedContentTokenCount", 0)}
                if finish == "MAX_TOKENS":
                    raise ProviderError("truncated", f"hit maxOutputTokens={max_out}")
                if finish in ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT") or not text:
                    raise ProviderError("blocked", f"finishReason={finish or 'empty'}")
                return Reply(text, model, finish, usage, {}, ms)
            msg = r.text[:600]
            low = msg.lower()
            if "api key not valid" in low or "api_key_invalid" in low or "api key expired" in low:
                raise ProviderError("auth", f"HTTP {r.status_code}: key rejected")
            if r.status_code == 400 and self.per_part_res and "mediaresolution" in low.replace("_", ""):
                Gemini.per_part_res = False
                continue
            if r.status_code == 400 and self.thinking and "thinking" in low:
                Gemini.thinking = False
                continue
            if r.status_code == 429:
                delay = 0.0
                m = re.search(r'"retryDelay":\s*"(\d+(?:\.\d+)?)s"', r.text)
                if m:
                    delay = float(m.group(1))
                kind = "quota_day" if re.search(r"perday|per_day|requestsperday|per day", low.replace(" ", "")) else "rate"
                raise ProviderError(kind, msg[:200], delay)
            if r.status_code in (401, 403):
                raise ProviderError("auth", f"HTTP {r.status_code}")
            if r.status_code == 404:
                raise ProviderError("bad_request", f"model {model} not found")
            if r.status_code in (500, 502, 503, 504):
                overloads += 1
                if overloads <= len(OVERLOAD_BACKOFF):     # be patient with the same model before switching
                    from . import keys
                    wait = OVERLOAD_BACKOFF[overloads - 1]
                    keys.notify(f"{model} busy (HTTP {r.status_code}); retrying the same model in {wait:.0f}s "
                                f"({overloads}/{len(OVERLOAD_BACKOFF)})")
                    time.sleep(wait)
                    continue
                busy = "high demand" in low or "overloaded" in low or r.status_code == 503
                raise ProviderError("overloaded" if busy else "server", f"HTTP {r.status_code}: {_brief(msg)}")
            raise ProviderError("server" if r.status_code >= 500 else "bad_request", f"HTTP {r.status_code}: {_brief(msg)}")
        raise ProviderError("server", "retries exhausted")


OVERLOAD_BACKOFF = (5.0, 15.0, 30.0)                # seconds between retries of a busy model


def _brief(msg: str) -> str:
    """The provider's error message, without the JSON wrapping."""
    m = re.search(r'"message":\s*"([^"]{1,220})', msg)
    return m.group(1) if m else msg[:200]


# --------------------------------------------------------------------------- Groq (OpenAI-compatible)
class Groq:
    def __init__(self, buckets: budget.Buckets):
        self.http = _http()
        self.buckets = buckets
        self._models: list[str] | None = None
        self.drop: set[str] = set()           # params a model rejected this session

    def models(self, key: str) -> list[str]:
        if self._models is None:
            r = self.http.get(f"{GROQ_BASE}/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code != 200:
                raise ProviderError("auth" if r.status_code in (401, 403) else "server", f"list models HTTP {r.status_code}")
            self._models = [m["id"] for m in r.json().get("data", [])]
        return self._models

    @staticmethod
    def extra(model: str) -> dict:
        m = model.lower()
        if m.startswith("openai/gpt-oss"):
            return {"reasoning_effort": "low", "include_reasoning": False}
        if m.startswith("qwen/"):
            return {"reasoning_effort": "none"}
        return {}

    def chat(self, model: str, messages: list[dict], *, key: str, kid: str = "", schema: dict | None = None,
             name: str = "out", max_out: int = 2500, temperature: float = 0.4, strict: bool = True,
             timeout: float = 90.0) -> Reply:
        """strict=True: constrained decoding against the schema. strict=False (the retry after a
        json_validate_failed): JSON-object mode with the schema stated in a system message; the pipeline validates."""
        if not key:
            raise ProviderError("auth", "no Groq key")
        body = {"model": model, "messages": messages, "max_completion_tokens": max_out, "temperature": temperature,
                **self.extra(model)}
        if schema is not None and strict:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": name, "strict": True, "schema": sc.provider_schema(schema)}}
        elif schema is not None:
            body["response_format"] = {"type": "json_object"}
            body["messages"] = [{"role": "system", "content": "Reply with ONE JSON object that matches this JSON "
                                 "schema exactly (every property, enum values only):\n" + json.dumps(
                                     sc.inline_refs(sc.provider_schema(schema)), separators=(",", ":"))}] + messages
        for attempt in range(4):
            for p in self.drop:
                body.pop(p, None)
            t0 = time.time()
            try:
                r = self.http.post(f"{GROQ_BASE}/chat/completions", json=body,
                                   headers={"Authorization": f"Bearer {key}"}, timeout=httpx.Timeout(timeout, connect=15))
            except httpx.TimeoutException as e:
                raise ProviderError("timeout", f"no reply within {timeout:.0f}s ({type(e).__name__})") from None
            except httpx.HTTPError as e:
                if attempt < 2:
                    time.sleep(2 ** attempt)
                    continue
                raise ProviderError("network", f"{type(e).__name__}: {e}") from None
            ms = int((time.time() - t0) * 1000)
            self.buckets.update(model, dict(r.headers), kid)
            if r.status_code == 200:
                d = r.json()
                ch = d["choices"][0]
                u = d.get("usage", {})
                usage = {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0),
                         "cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
                         "thinking": (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0)}
                if ch.get("finish_reason") == "length":
                    raise ProviderError("truncated", f"hit max_completion_tokens={max_out}")
                return Reply(ch["message"].get("content") or "", model, ch.get("finish_reason", ""), usage,
                             {k: v for k, v in r.headers.items() if k.lower().startswith("x-ratelimit")}, ms)
            msg = r.text[:600]
            low = msg.lower()
            if r.status_code == 400:
                bad = [p for p in ("reasoning_effort", "include_reasoning") if p in low and p in body]
                if bad:
                    self.drop.update(bad)
                    continue
                if "json_validate_failed" in low or "failed to generate json" in low:
                    raise ProviderError("bad_output", "the model's JSON failed the schema (json_validate_failed)")
                raise ProviderError("bad_request", _brief(msg))
            if r.status_code == 413 or "request too large" in low:
                raise ProviderError("too_large", _brief(msg))
            if r.status_code == 429:
                ra = float(r.headers.get("retry-after") or 0)
                day = r.headers.get("x-ratelimit-remaining-requests") == "0" or re.search(
                    r"per day|\(rpd\)|\(tpd\)|tokens per day|requests per day", low)
                raise ProviderError("quota_day" if day else "rate", _brief(msg), ra)
            if r.status_code in (401, 403):
                raise ProviderError("auth", f"HTTP {r.status_code}")
            if r.status_code == 404:
                raise ProviderError("bad_request", f"model {model} not found")
            if r.status_code >= 500 and attempt < 1:
                time.sleep(4)
                continue
            raise ProviderError("overloaded" if r.status_code == 503 else "server" if r.status_code >= 500 else
                                "bad_request", f"HTTP {r.status_code}: {_brief(msg)}")
        raise ProviderError("server", "retries exhausted")
