"""eta.py - the Studio's "about N min left": the pipeline's steps, each with a typical duration that finished jobs
keep up to date (moving average on disk), so the estimate follows the models actually answering these days.

    route    split + lab routing + references + images uploaded       a1 .. a4   the agents
    a5       the composer writes the page                             check      the page measured in a browser
    repair   A5's one fix round (only when it starts)                  fallback   the backup page (only when it starts)
    publish  preview screenshot + upload

remaining = what's left of the current step (never less than a sliver: a step isn't over until it ends) + the typical
time of every step still ahead. Starting values: the median call times of 42 runs on this PC (2026-11-22) and the
server's routing time; each finished job then pulls a step's value 30% toward what it took.
"""
from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path

BASE = ("route", "a1", "a2", "a3", "a4", "a5", "check", "publish")   # every job; repair / fallback when they start
DEFAULT_S = {"route": 55.0, "a1": 75.0, "a2": 8.0, "a3": 10.0, "a4": 8.0, "a5": 150.0, "check": 25.0,
             "repair": 140.0, "fallback": 30.0, "publish": 15.0}
ALPHA = 0.3
MIN_LEARN_S = 2.0                     # a cached step (0 s) says nothing about the next job's time
FILE = Path(os.getenv("LANDING_TIMING", str(Path(os.getenv("LANDING_LEDGER", r"D:\serpman-studio\out\_agents\quota.json"))
                                            .with_name("timing.json"))))
_lock = threading.Lock()


def load(path: Path | None = None) -> dict[str, float]:
    try:
        d = json.loads(Path(path or FILE).read_text(encoding="utf-8"))
        return {k: float(v) for k, v in d.items() if k in DEFAULT_S and isinstance(v, (int, float)) and v > 0}
    except Exception:  # noqa: BLE001
        return {}


class Eta:
    def __init__(self, path: Path | None = None, clock=time.time):
        self.path, self.clock = Path(path or FILE), clock
        self.est = {**DEFAULT_S, **load(self.path)}
        self.t0 = self.step_t = clock()
        self.step = "route"
        self.spent: dict[str, float] = {}
        self.extra: list[str] = []            # repair / fallback, once they start

    def order(self) -> list[str]:
        o = list(BASE)
        for s in self.extra:
            o.insert(o.index("publish"), s)
        return o

    def enter(self, step: str) -> None:
        if step == self.step or step not in DEFAULT_S:
            return
        now = self.clock()
        self.spent[self.step] = self.spent.get(self.step, 0.0) + now - self.step_t
        if step in ("repair", "fallback") and step not in self.extra:
            self.extra.append(step)
        self.step, self.step_t = step, now

    def remaining(self) -> int:
        o, now = self.order(), self.clock()
        i = o.index(self.step) if self.step in o else 0
        cur = self.est[self.step]
        left = max(0.15 * cur, cur - (now - self.step_t))
        return int(round(left + sum(self.est[s] for s in o[i + 1:])))

    def stamp(self) -> dict:
        """What every progress event carries: the step, seconds left, seconds so far, the server's clock (ms)."""
        now = self.clock()
        return {"step": self.step, "eta_s": self.remaining(), "elapsed_s": int(now - self.t0), "at": int(now * 1000)}

    def finish(self, ok: bool = True) -> None:
        """Close the last step; a finished job moves each step's typical time toward what it took (saved)."""
        now = self.clock()
        self.spent[self.step] = self.spent.get(self.step, 0.0) + now - self.step_t
        self.step_t = now
        if not ok:
            return
        with _lock:
            est = {**DEFAULT_S, **load(self.path)}
            for s, v in self.spent.items():
                if s in est and v >= MIN_LEARN_S:
                    est[s] = round((1 - ALPHA) * est[s] + ALPHA * v, 1)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(est, indent=1), encoding="utf-8")
                tmp.replace(self.path)
            except OSError:
                pass


# --------------------------------------------------------------------------- what the Studio shows for each event
NAMES = {"gemini-4-hydrogen": "Gemini 4 Hydrogen", "gemini-3.8-flash": "Gemini 3.8 Flash",
         "gemini-3.6-flash": "Gemini 3.6 Flash", "gemma-4-31b-it": "Gemma 4 31B", "gemma-4-26b-a4b-it": "Gemma 4 26B",
         "inclusionai/ling-3.2-flash:free": "Ling 3.2 Flash", "nvidia/nemotron-3.5-super-vl:free": "Nemotron VL",
         "nvidia/nemotron-3-ultra-550b-a55b:free": "Nemotron Ultra", "openai/gpt-oss-120b": "GPT-OSS 120B",
         "qwen/qwen3.8-27b": "Qwen 3.8", "ministral-14b-latest": "Ministral 14B", "ministral-8b-latest": "Ministral 8B",
         "codestral-latest": "Codestral", "mistral-medium-latest": "Mistral Medium"}
STEP_TEXT = {"a1": "Reading the reference images", "a2": "Planning the layout", "a3": "Writing the copy",
             "a4": "Drawing the decoration", "a5": "Composing the page", "check": "Checking the page in a browser",
             "repair": "Fixing what the browser found", "fallback": "Building the backup page"}


def model_name(model: str | None) -> str:
    m = (model or "").removeprefix("openrouter/")
    if m.startswith("modal/"):
        return "your GPU (" + m.split("/")[-1].split("-Instruct")[0] + ")"
    return NAMES.get(m, m.split("/")[-1])


def describe(ev: dict, prev_model: dict[str, str]) -> str | None:
    """A pipeline progress event -> one short Studio line (None: nothing new to say)."""
    k, agent = ev.get("kind"), ev.get("agent")
    if k == "start":
        return STEP_TEXT.get(agent)
    if k == "try":
        name, was = model_name(ev.get("model")), prev_model.get(agent)
        prev_model[agent] = name
        base = STEP_TEXT.get(agent, agent)
        return f"{base} · {was} is busy, switched to {name}" if was and was != name else f"{base} · {name}"
    if k == "done" and ev.get("source") in ("model", "repaired") and ev.get("ms"):
        return f"{STEP_TEXT.get(agent, agent)} · done by {model_name(ev.get('model'))} in {ev['ms'] / 1000:.0f} s"
    if k == "retry":
        why = {"truncated": "ran out of room, retrying with more", "timeout": "is slow, asking once more"}
        return f"{STEP_TEXT.get(agent, agent)} · {model_name(ev.get('model'))} {why.get(ev.get('why'), 'retrying')}"
    if k == "check":
        return STEP_TEXT["check"]
    return None
