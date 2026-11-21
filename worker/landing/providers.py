"""providers.py - the free-tier providers, over plain httpx (no SDKs).

Mistral (La Plateforme, OpenAI-compatible; the primary for A1 / A5 and the backup for A2-A4): images as content parts,
strict json_schema, ~1 request/s per key (paced), 429 month-limit -> quota_day.

Gemini (Google AI Studio, generateContent v1beta; now only the last fallback for A1 / A5): multimodal parts, responseJsonSchema, per-part media resolution
(falls back to the global setting if the API rejects it), thinking level per call (low by default; the composer and the director think more).
Groq (OpenAI-compatible, same base class as Mistral): strict json_schema (constrained decoding), reasoning kept low/off and hidden, images as
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
MISTRAL_BASE = os.getenv("MISTRAL_BASE", "https://api.mistral.ai/v1").rstrip("/")
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


# --------------------------------------------------------------------------- OpenAI-compatible chat (Groq, Mistral)
class OpenAICompat:
    """POST {base}/chat/completions with strict json_schema (or JSON-object mode), errors mapped to ProviderError.
    Subclasses set the base URL, the name, the max-tokens field, per-model extras and provider-specific 400/429 text."""
    base = ""
    name = ""
    max_field = "max_completion_tokens"
    drop_params = ("reasoning_effort", "include_reasoning")
    pace_s = 0.0                              # minimum seconds between requests per key (Mistral: ~1 request/s)

    def __init__(self, buckets: budget.Buckets):
        self.http = _http()
        self.buckets = buckets
        self._models: list[str] | None = None
        self._caps: dict[str, dict] = {}
        self.drop: set[str] = set()           # params a model rejected this session

    def models(self, key: str) -> list[str]:
        if self._models is None:
            r = self.http.get(f"{self.base}/models", headers={"Authorization": f"Bearer {key}"})
            if r.status_code != 200:
                raise ProviderError("auth" if r.status_code in (401, 403) else "server", f"list models HTTP {r.status_code}")
            data = r.json().get("data", [])
            self._models = [m["id"] for m in data]
            self._caps = {m["id"]: (m.get("capabilities") or {}) for m in data}
            for m in data:                    # Mistral lists aliases (mistral-large-latest) on the model they point to
                for a in m.get("aliases") or []:
                    self._caps.setdefault(a, m.get("capabilities") or {})
                    if a not in self._models:
                        self._models.append(a)
        return self._models

    def extra(self, model: str) -> dict:
        return {}

    def bad_schema(self, low: str) -> bool:
        return "json_validate_failed" in low or "failed to generate json" in low

    def chat(self, model: str, messages: list[dict], *, key: str, kid: str = "", schema: dict | None = None,
             name: str = "out", max_out: int = 2500, temperature: float = 0.4, strict: bool = True,
             timeout: float = 90.0) -> Reply:
        """strict=True: constrained decoding against the schema. strict=False (the retry after a
        json_validate_failed): JSON-object mode with the schema stated in a system message; the pipeline validates."""
        if not key:
            raise ProviderError("auth", f"no {self.name} key")
        body = {"model": model, "messages": messages, self.max_field: max_out, "temperature": temperature,
                **self.extra(model)}
        if schema is not None and strict:
            body["response_format"] = {"type": "json_schema",
                                       "json_schema": {"name": name, "strict": True, "schema": sc.provider_schema(schema)}}
        elif schema is not None:
            body["response_format"] = {"type": "json_object"}
            body["messages"] = [{"role": "system", "content": "Reply with ONE JSON object that matches this JSON "
                                 "schema exactly (every property, enum values only):\n" + json.dumps(
                                     sc.inline_refs(sc.provider_schema(schema)), separators=(",", ":"))}] + messages
        overloads = 0
        for attempt in range(7):
            for p in self.drop:
                body.pop(p, None)
            if self.pace_s:
                self.buckets.pace(self.name, kid, self.pace_s)
            t0 = time.time()
            try:
                r = self.http.post(f"{self.base}/chat/completions", json=body,
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
            special = self.special(r, low, model)
            if special is not None:
                raise special
            if r.status_code in (400, 422):
                bad = [p for p in self.drop_params if p in low and p in body]
                if bad:
                    self.drop.update(bad)
                    continue
                if self.bad_schema(low):
                    raise ProviderError("bad_output", f"the model's JSON failed the schema ({_brief(msg)[:120]})")
                raise ProviderError("bad_request", _brief(msg))
            if r.status_code == 413 or "request too large" in low:
                raise ProviderError("too_large", _brief(msg))
            if r.status_code == 429:
                ra = float(r.headers.get("retry-after") or 0)
                raise ProviderError("quota_day" if self.daily(r, low) else "rate", _brief(msg), ra)
            if r.status_code in (401, 403):
                raise ProviderError("auth", f"HTTP {r.status_code}")
            if r.status_code == 404:
                raise ProviderError("bad_request", f"model {model} not found")
            if r.status_code >= 500:
                overloads += 1
                backoff = self.backoff()
                if overloads <= len(backoff):
                    wait = backoff[overloads - 1]
                    if wait >= 5:
                        from . import keys
                        keys.notify(f"{model} busy (HTTP {r.status_code}); retrying the same model in {wait:.0f}s "
                                    f"({overloads}/{len(backoff)})")
                    time.sleep(wait)
                    continue
            raise ProviderError("overloaded" if r.status_code == 503 else "server" if r.status_code >= 500 else
                                "bad_request", f"HTTP {r.status_code}: {_brief(msg)}")
        raise ProviderError("server", "retries exhausted")

    def special(self, r: httpx.Response, low: str, model: str) -> ProviderError | None:
        """Provider-specific errors checked before the generic mapping (None = use the generic one)."""
        return None

    def daily(self, r: httpx.Response, low: str) -> bool:
        return bool(r.headers.get("x-ratelimit-remaining-requests") == "0" or re.search(
            r"per day|\(rpd\)|\(tpd\)|tokens per day|requests per day", low))

    def backoff(self) -> tuple:
        return (4.0,)


class Groq(OpenAICompat):
    base = GROQ_BASE
    name = "groq"

    def extra(self, model: str) -> dict:
        m = model.lower()
        if m.startswith("openai/gpt-oss"):
            return {"reasoning_effort": "low", "include_reasoning": False}
        if m.startswith("qwen/"):
            return {"reasoning_effort": "none"}
        return {}


# --------------------------------------------------------------------------- Mistral (La Plateforme, OpenAI-compatible)
class Mistral(OpenAICompat):
    """Free plan, as measured on the user's key (2026-11-21): limits are per model and per workspace. Ministral 14B /
    8B and Codestral get 2 requests/min and 40K tokens/min; Medium, Small, Large and Magistral answer 429 with
    x-ratelimit-limit-req-minute: 0 (or 403 tier_not_allowed): not available on this tier, which is NOT a key
    problem -> kind "unavailable" (the router skips that model for this key and keeps the key for the others).
    Vision models take images as {"type": "image_url", "image_url": "data:image/jpeg;base64,..."} (<=1540 px).
    A per-minute 429 carries no retry-after: 60 s is assumed. A monthly-limit 429 marks the key out for the day."""
    base = MISTRAL_BASE
    name = "mistral"
    max_field = "max_tokens"
    drop_params = ()
    pace_s = 1.1

    def bad_schema(self, low: str) -> bool:
        return super().bad_schema(low) or ("response_format" in low or "json_schema" in low or "schema" in low)

    def special(self, r: httpx.Response, low: str, model: str) -> ProviderError | None:
        h = {k.lower(): v for k, v in r.headers.items()}
        if r.status_code == 403 and ("tier_not_allowed" in low or "not available in your subscription" in low):
            return ProviderError("unavailable", f"{model} is not available on this key's subscription tier")
        if r.status_code == 429 and h.get("x-ratelimit-limit-req-minute", "").strip() in ("0", "0.0"):
            return ProviderError("unavailable", f"{model} has a limit of 0 requests/min on this key's tier")
        if r.status_code == 429 and not self.daily(r, low):
            ra = float(h.get("retry-after") or 0) or 60.0
            return ProviderError("rate", _brief(r.text[:600]), ra)
        return None

    def daily(self, r: httpx.Response, low: str) -> bool:
        h = {k.lower(): v for k, v in r.headers.items()}
        month_left = [v for k, v in h.items() if "remaining" in k and "month" in k]
        return bool(re.search(r"month|per day|daily", low) or any(v.strip() in ("0", "0.0") for v in month_left))

    def backoff(self) -> tuple:
        return OVERLOAD_BACKOFF

    def vision(self, model: str) -> bool:
        return bool(self._caps.get(model, {}).get("vision"))


def image_part(path: str | Path, side: int) -> dict:
    """An OpenAI-style image content part as Mistral takes it (the URL as a plain string)."""
    return {"type": "image_url", "image_url": f"data:image/jpeg;base64,{jpeg_b64(path, side)}"}
