"""keys.py - API keys for the landing agents: several per provider, failover when one hits a limit.

Where keys come from (environment first, then the gitignored env file; values are never printed or logged):
    OPENROUTER_API_KEY=k1   (A1 / A5 first)   MISTRAL_API_KEY=k1   GROQ_API_KEY=k1   GEMINI_API_KEY=k1 (last fallback)
    OPENROUTER_API_KEY_2=k2  ...      MISTRAL_API_KEY_2=k2  ...         GROQ_API_KEY_2=k2  ...   GEMINI_API_KEY_2=k2  ...
    OPENROUTER_API_KEYS=k1,k2         MISTRAL_API_KEYS=k1,k2            GROQ_API_KEYS=k1,k2      GEMINI_API_KEYS=k1,k2,k3
    (comma / semicolon / space separated)
Env file: LANDING_ENV_FILE, default D:\\serpman-studio\\worker\\.env (the worker's own .env; the lab reads it too).

Limits are per Google Cloud PROJECT (Gemini), per ORGANIZATION (Groq), per WORKSPACE (Mistral) and per ACCOUNT
(OpenRouter's free pool), not per key: keys from the same project /
org share one quota and fail together. Backup keys help only when they come from another project / org (e.g. a
paid key as the last resort). On a limit the pipeline moves to the next key and prints one line to the terminal:
    21:04:11 [landing] gemini key 1/3 reached its daily limit for gemini-3.8-flash (resets at midnight Pacific) -> using gemini key 2/3
Keys are identified in logs, the ledger and the UI only by position and a short hash.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

ENV_FILE = Path(os.getenv("LANDING_ENV_FILE", r"D:\serpman-studio\worker\.env"))
NAME = re.compile(r"^(GEMINI|GROQ|MISTRAL|OPENROUTER)_API_KEY(S|_\d+)?$")
# process-wide (and kept across the lab's hot reloads): a rejected key stays skipped and a cooling key keeps
# cooling for the life of the serve / worker process, not just one pipeline run. Keyed by kid, never by value.
_announced: set[str] = globals().get("_announced", set())
_DISABLED: dict[str, str] = globals().get("_DISABLED", {})
_COOL: dict[tuple[str, str], float] = globals().get("_COOL", {})
# (kid, model) -> (until, why): a model this key's tier doesn't offer (Mistral limit 0 / tier_not_allowed). The key
# stays usable for every other model; the model is rechecked after UNAVAILABLE_S (in case the plan changes).
_UNAVAIL: dict[tuple[str, str], tuple[float, str]] = globals().get("_UNAVAIL", {})
UNAVAILABLE_S = 6 * 3600.0
# kept on disk too (wall-clock expiry), so a worker / lab restart doesn't spend a request re-learning it
UNAVAIL_FILE = Path(os.getenv("LANDING_UNAVAIL", r"D:\serpman-studio\out\_agents\unavailable.json"))


def _unavail_disk() -> dict:
    try:
        d = json.loads(Path(os.getenv("LANDING_UNAVAIL", str(UNAVAIL_FILE))).read_text(encoding="utf-8"))
        return {k: v for k, v in d.items() if v.get("until", 0) > time.time()}
    except Exception:  # noqa: BLE001
        return {}


def notify(msg: str) -> None:
    """One line on the terminal that started serve / the worker (stderr, flushed, timestamped)."""
    print(f"{time.strftime('%H:%M:%S')} [landing] {msg}", file=sys.stderr, flush=True)


def _file_vars() -> dict[str, str]:
    path = Path(os.getenv("LANDING_ENV_FILE", str(ENV_FILE)))
    out = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                if NAME.match(k):
                    out[k] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def _order(name: str) -> tuple:
    m = re.search(r"_(\d+)$", name)
    return (0, 0) if name.endswith("_API_KEY") else (1, int(m.group(1))) if m else (2, 0)


def collect(provider: str) -> list[str]:
    """All keys for 'openrouter', 'mistral', 'groq' or 'gemini', in order: X_API_KEY, X_API_KEY_2.., X_API_KEYS; duplicates dropped."""
    prefix = provider.upper() + "_API_KEY"
    src = {**_file_vars(), **{k: v for k, v in os.environ.items() if NAME.match(k)}}
    vals = []
    for k in sorted((k for k in src if k.startswith(prefix)), key=_order):
        vals += [x for x in re.split(r"[,;\s]+", src[k]) if x]
    return list(dict.fromkeys(vals))


def kid(key: str) -> str:
    return hashlib.sha1(key.encode()).hexdigest()[:8]


class Ring:
    """The keys of one provider, tried in order; a key out of a model's daily quota is skipped for that model
    (ledger), a key that hit the per-minute limit cools down, a rejected key is skipped for the session."""

    def __init__(self, provider: str):
        self.provider = provider
        self.keys = collect(provider) if provider else []
        self.ids = [kid(k) for k in self.keys]
        sig = provider + ":" + ",".join(self.ids)
        if self.keys and sig not in _announced:          # once per process, again only if the key set changes
            _announced.add(sig)
            notify(f"{provider}: {len(self.keys)} key(s) loaded" + (" (failover order 1..n)" if len(self.keys) > 1 else ""))

    @property
    def disabled(self) -> dict[int, str]:
        return {i: _DISABLED[k] for i, k in enumerate(self.ids) if k in _DISABLED}

    def __len__(self) -> int:
        return len(self.keys)

    def label(self, i: int) -> str:
        return f"{self.provider} key {i + 1}/{len(self.keys)}"

    def order(self, model: str, ledger) -> list[int]:
        """Usable keys for this model: not rejected, not out of today's quota; cooling keys go last (shortest first)."""
        ok = [i for i in range(len(self.keys)) if self.ids[i] not in _DISABLED
              and not self.unavailable(i, model) and ledger.left(model, self.ids[i])["requests"] > 0]
        return sorted(ok, key=lambda i: (self.cooling_for(i, model), i))

    def cooling_for(self, i: int, model: str) -> float:
        return max(0.0, _COOL.get((self.ids[i], model), 0.0) - time.monotonic())

    def cool_down(self, i: int, model: str, seconds: float) -> None:
        _COOL[(self.ids[i], model)] = time.monotonic() + max(5.0, seconds or 60.0)

    def unavailable(self, i: int, model: str) -> bool:
        u = _UNAVAIL.get((self.ids[i], model))
        if u and u[0] > time.monotonic():
            return True
        d = _unavail_disk().get(f"{self.ids[i]}|{model}")
        if d:                                            # learned by an earlier process: adopt it for the rest
            _UNAVAIL[(self.ids[i], model)] = (time.monotonic() + d["until"] - time.time(), d.get("why", ""))
            return True
        return False

    def mark_unavailable(self, i: int, model: str, why: str) -> None:
        _UNAVAIL[(self.ids[i], model)] = (time.monotonic() + UNAVAILABLE_S, why[:200])
        p = Path(os.getenv("LANDING_UNAVAIL", str(UNAVAIL_FILE)))
        try:
            d = _unavail_disk()
            d[f"{self.ids[i]}|{model}"] = {"until": time.time() + UNAVAILABLE_S, "why": why[:200]}
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(d, indent=1), encoding="utf-8")
            os.replace(tmp, p)
        except OSError:
            pass

    def disable(self, i: int, why: str) -> None:
        _DISABLED[self.ids[i]] = why[:200]
