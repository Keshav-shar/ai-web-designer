"""budget.py - free-tier budgets: token estimates, per-model token buckets from response headers, a daily ledger.

Free-tier limits (verified 2026-11-20; Groq: console.groq.com/docs/rate-limits; Gemini: AI Studio's rate-limit page
as reported Oct 2026; Google no longer prints them, so your project's page wins). Limits are per MODEL (Groq: per
org, Gemini: per project), which is why the agents are spread over different models. Live headers and 429s
override this table: the ledger marks a model exhausted for the day on a daily-quota 429.
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path

LIMITS = {
    "gemini-4-hydrogen": {"rpm": 5, "rpd": 20, "tpm": 250_000},   # assumed like Flash; the ledger learns the real cap
    "gemini-3.8-flash": {"rpm": 5, "rpd": 20, "tpm": 250_000},
    "gemini-3.7-flash": {"rpm": 5, "rpd": 20, "tpm": 250_000},
    "gemini-3.6-flash": {"rpm": 5, "rpd": 20, "tpm": 250_000},
    "gemini-3.5-flash": {"rpm": 5, "rpd": 20, "tpm": 250_000},
    "gemini-2.5-flash": {"rpm": 5, "rpd": 20, "tpm": 250_000},
    "gemini-2.5-flash-lite": {"rpm": 10, "rpd": 20, "tpm": 250_000},
    "gemini-3.5-flash-lite": {"rpm": 15, "rpd": 500, "tpm": 250_000},
    "gemini-3.1-flash-lite": {"rpm": 15, "rpd": 500, "tpm": 250_000},
    # Mistral free plan, measured on the user's key 2026-11-21 (x-ratelimit-*-minute headers): Ministral 14B / 8B and
    # Codestral 2 req/min + 40K tokens/min each (separate pools per model); Medium / Small / Large: 0 (not on the tier).
    "ministral-14b-latest": {"rpm": 2, "rpd": 2000, "tpm": 40_000},
    "ministral-8b-latest": {"rpm": 2, "rpd": 2000, "tpm": 40_000},
    "codestral-latest": {"rpm": 2, "rpd": 2000, "tpm": 40_000},
    "mistral-medium-latest": {"rpm": 2, "rpd": 2000, "tpm": 40_000},     # if the tier opens it: assume the same
    "openai/gpt-oss-120b": {"rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200_000},
    "openai/gpt-oss-20b": {"rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200_000},
    "qwen/qwen3.8-27b": {"rpm": 30, "rpd": 1000, "tpm": 8000, "tpd": 200_000},
}
DEFAULT = {"rpm": 10, "rpd": 200, "tpm": 8000}
MODAL_LIMITS = {"rpm": 1000, "rpd": 1_000_000, "tpm": 50_000_000}   # the user's own GPU (Modal): no shared pool
# OpenRouter (openrouter.ai/docs/api-reference/limits, read 2026-11-22): free ':free' models allow 20 requests/min and
# a per-ACCOUNT daily pool shared by every free model: 50 requests, or 1000 once $10 of credit was ever bought.
# GET /key reports the pool (free_model_daily_requests); pipeline.Ctx adopts it with set_free_daily() / Ledger.sync().
OR_PREFIX = "openrouter/"               # pipeline ids: 'openrouter/<vendor>/<model>' (Groq ids contain '/' too)
OR_FREE_POOL = OR_PREFIX + ":free"      # the one ledger slot every free OpenRouter model counts against
OPENROUTER_FREE = {"rpm": 20, "rpd": 50, "tpm": 2_000_000}      # no token window on the free tier; context is large
OPENROUTER_PAID = {"rpm": 60, "rpd": 100_000, "tpm": 2_000_000}
OR_IMAGE = {"low": 1300, "medium": 2000, "high": 3200}           # rough per-image token estimate at detail 'high'
GEMINI_IMAGE = {"low": 280, "medium": 560, "high": 1120, "ultra_high": 2240}
MISTRAL_IMAGE = {"low": 1000, "medium": 1000, "high": 2200}   # measured: a 1024 px image ~950 tokens on Ministral
QWEN_IMAGE = 2048                     # Groq: each image counts as 2048 input tokens
MARGIN = 0.9                          # never plan to use more than 90% of a minute's tokens in one request
LEDGER = Path(os.getenv("LANDING_LEDGER", r"D:\serpman-studio\out\_agents\quota.json"))


MISTRAL_DEFAULT = {"rpm": 2, "rpd": 2000, "tpm": 40_000}


def is_or_free(model: str) -> bool:
    return model.startswith(OR_PREFIX) and model.endswith(":free")


def set_free_daily(limit: int | None) -> None:
    """The account's real daily pool of free OpenRouter requests (50 or 1000), as GET /key reports it."""
    if isinstance(limit, int) and limit > 0:
        OPENROUTER_FREE["rpd"] = limit


def limits(model: str) -> dict:
    if model in LIMITS:
        return LIMITS[model]
    if model.startswith(OR_PREFIX):
        return OPENROUTER_FREE if model.endswith(":free") else OPENROUTER_PAID
    if model.startswith("modal/"):
        return MODAL_LIMITS
    if model.startswith(("mistral", "ministral", "magistral", "pixtral", "devstral", "codestral")):
        return MISTRAL_DEFAULT
    return DEFAULT


def est_text(s: str) -> int:
    return math.ceil(len(s) / 3.5)


def pacific_day() -> str:
    """Gemini daily quotas reset at midnight Pacific; Groq's roll, so the Pacific date is a safe common key."""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/Los_Angeles"))
    except Exception:  # noqa: BLE001 - no tz database on this machine: UTC-8 (an hour early in summer, never late)
        now = datetime.now(timezone(timedelta(hours=-8)))
    return now.strftime("%Y-%m-%d")


def _dur(s: str | None) -> float:
    """Groq reset headers: '7.66s', '2m59.56s', '1h2m3s', '120ms'."""
    if not s:
        return 0.0
    total, num = 0.0, ""
    i = 0
    while i < len(s):
        c = s[i]
        if c.isdigit() or c == ".":
            num += c
        elif s[i:i + 2] == "ms":
            total += float(num or 0) / 1000
            num, i = "", i + 1
        elif c in "hms":
            total += float(num or 0) * {"h": 3600, "m": 60, "s": 1}[c]
            num = ""
        i += 1
    return total + (float(num) if num else 0.0)


def slot(model: str, kid: str = "") -> str:
    """Ledger / bucket key: limits belong to a model *per key's project / org*, so each key counts separately."""
    return f"{model}|{kid}" if kid else model


def day_slot(model: str, kid: str = "") -> str:
    """The daily ledger's key: like slot(), except that every free OpenRouter model shares one per-account pool."""
    return slot(OR_FREE_POOL if is_or_free(model) else model, kid)


class Ledger:
    """Requests and tokens per model per key per Pacific day, persisted on D: (shared by the lab and the worker).
    Keys appear only as short hashes (keys.kid)."""

    def __init__(self, path: Path | None = None):
        self.path, self.lock = Path(path or os.getenv("LANDING_LEDGER", str(LEDGER))), threading.Lock()

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            return {}

    def _save(self, d: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
        os.replace(tmp, self.path)

    def today(self) -> dict:
        return self._load().get(pacific_day(), {})

    def record(self, model: str, tokens: int, kid: str = "") -> None:
        with self.lock:
            d = self._load()
            day = d.setdefault(pacific_day(), {})
            m = day.setdefault(day_slot(model, kid), {"req": 0, "tok": 0})
            m["req"] += 1
            m["tok"] += int(tokens)
            for k in sorted(d)[:-7]:                  # keep a week
                d.pop(k, None)
            self._save(d)

    def exhaust(self, model: str, why: str, kid: str = "") -> None:
        with self.lock:
            d = self._load()
            d.setdefault(pacific_day(), {}).setdefault(day_slot(model, kid), {"req": 0, "tok": 0})["exhausted"] = why[:200]
            self._save(d)

    def sync(self, model: str, used: int, kid: str = "") -> None:
        """Adopt a provider-reported count of today's requests when it is higher than ours (other apps on the account)."""
        with self.lock:
            d = self._load()
            m = d.setdefault(pacific_day(), {}).setdefault(day_slot(model, kid), {"req": 0, "tok": 0})
            if int(used) > m["req"]:
                m["req"] = int(used)
                self._save(d)

    def left(self, model: str, kid: str = "") -> dict:
        m = self.today().get(day_slot(model, kid), {})
        L = limits(model)
        return {"requests": 0 if m.get("exhausted") else max(0, L["rpd"] - m.get("req", 0)),
                "tokens": max(0, L.get("tpd", 10 ** 9) - m.get("tok", 0)), "exhausted": m.get("exhausted")}

    def left_total(self, model: str, kids: list[str]) -> dict:
        """Across all keys of a provider (the lab UI's 'quota today')."""
        per = [self.left(model, k) for k in kids] or [self.left(model)]
        return {"requests": sum(x["requests"] for x in per), "keys": len(per),
                "exhausted": all(x["exhausted"] for x in per) and per[0]["exhausted"] or None,
                "keys_out": sum(1 for x in per if x["exhausted"] or x["requests"] <= 0)}


class Buckets:
    """Per-model minute windows: Groq headers when we have them (exact), else our own request/token history."""

    def __init__(self):
        self.lock = threading.Lock()
        self.hist: dict[str, deque] = {}          # model -> deque[(t, tokens)]
        self.hdr: dict[str, dict] = {}            # model -> {"tok": remaining, "reset_at": t}
        self.last: dict[str, float] = {}          # provider|key -> monotonic time of the last request (pace)

    def pace(self, provider: str, kid: str, min_interval: float) -> float:
        """Keep at least min_interval seconds between two requests on one key (Mistral: ~1 request/s). -> slept s."""
        k = slot(provider, kid)
        with self.lock:
            now = time.monotonic()
            wait = max(0.0, self.last.get(k, -1e9) + min_interval - now)
            self.last[k] = now + wait
        if wait:
            time.sleep(wait)
        return wait

    def update(self, model: str, headers: dict, kid: str = "") -> None:
        h = {k.lower(): v for k, v in (headers or {}).items()}
        model = slot(model, kid)
        if "x-ratelimit-remaining-tokens" in h:
            with self.lock:
                self.hdr[model] = {"tok": int(float(h["x-ratelimit-remaining-tokens"])),
                                   "reset_at": time.monotonic() + _dur(h.get("x-ratelimit-reset-tokens"))}
        elif "x-ratelimit-remaining-tokens-minute" in h:          # Mistral: no reset header -> a minute at most
            with self.lock:
                self.hdr[model] = {"tok": int(float(h["x-ratelimit-remaining-tokens-minute"])),
                                   "reset_at": time.monotonic() + 60.0}

    def note(self, model: str, tokens: int, kid: str = "") -> None:
        with self.lock:
            self.hist.setdefault(slot(model, kid), deque()).append((time.monotonic(), tokens))

    def wait_for(self, model: str, need: int, kid: str = "") -> float:
        """Seconds to wait before a request of `need` tokens fits this model's minute window for this key
        (inf = never fits)."""
        L = limits(model)
        model = slot(model, kid)
        if need > L["tpm"] * MARGIN:
            return math.inf
        now = time.monotonic()
        with self.lock:
            q = self.hist.setdefault(model, deque())
            while q and now - q[0][0] > 60:
                q.popleft()
            wait = 0.0
            if len(q) >= L["rpm"]:
                wait = max(wait, 60 - (now - q[0][0]))
            used = sum(t for _, t in q)
            if used + need > L["tpm"] * MARGIN and q:
                acc, cut = used, None
                for t0, tok in q:                    # wait until enough old requests age out
                    acc -= tok
                    if acc + need <= L["tpm"] * MARGIN:
                        cut = t0
                        break
                wait = max(wait, 60 - (now - (cut if cut is not None else q[-1][0])))
            hd = self.hdr.get(model)
            if hd and hd["reset_at"] > now and hd["tok"] < need:
                wait = max(wait, hd["reset_at"] - now)
        return max(0.0, wait)
