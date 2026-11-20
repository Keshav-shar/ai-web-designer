"""cache.py - agent outputs cached by input hash, so a lab Rebuild or a what-if costs zero model calls.

key = sha1(prompt version, agent, prompt text, schema, slice, image refs). Editing one agent's prompt or input
invalidates that agent and (through their changed inputs) everything downstream, nothing upstream.
AGENTS_REPLAY=<dir>: read-only replay of a recorded run (tests; a miss is an error, never a network call).
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import PROMPT_VERSION

ROOT = Path(os.getenv("LANDING_CACHE", r"D:\serpman-studio\out\_agents\cache"))


class ReplayMiss(RuntimeError):
    pass


def replay_dir() -> Path | None:
    r = os.getenv("AGENTS_REPLAY", "").strip()
    return Path(r) if r else None


def key(agent: str, *parts) -> str:
    h = hashlib.sha1(f"{PROMPT_VERSION}|{agent}".encode())
    for p in parts:
        h.update(b"\x00" + (p if isinstance(p, str) else json.dumps(p, sort_keys=True, default=str)).encode())
    return h.hexdigest()[:20]


def _path(base: Path, agent: str, k: str) -> Path:
    return base / agent / f"{k}.json"


def get(agent: str, k: str) -> dict | None:
    rd = replay_dir()
    f = _path(rd or ROOT, agent, k)
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    if rd:
        raise ReplayMiss(f"replay has no {agent} record {k}")
    return None


def drop(agent: str, k: str) -> None:
    """Evict a record (e.g. an A5 page the browser QA rejected)."""
    if replay_dir():
        return
    f = _path(ROOT, agent, k)
    if f.exists():
        f.unlink()


def put(agent: str, k: str, record: dict) -> None:
    if replay_dir():
        return
    f = _path(ROOT, agent, k)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)
