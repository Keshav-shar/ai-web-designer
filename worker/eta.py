"""eta.py - the Studio's "about N min left": the pipeline's steps, each with a typical duration that finished jobs
keep up to date (moving average on disk), so the estimate follows the models actually answering these days.

    route    split + lab routing + references + images uploaded       a1 .. a4   the agents
    a5       the composer writes the page                             check      the page measured in a browser
    a6       the improver: looks at the rendered page, returns it improved (and measured)
    repair   A5's fix round, only when its page can't render           fallback   the backup page (only when it starts)
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

BASE = ("route", "a1", "a2", "a3", "a4", "a5", "check", "a6", "publish")   # repair / fallback when they start
DEFAULT_S = {"route": 55.0, "a1": 75.0, "a2": 8.0, "a3": 10.0, "a4": 8.0, "a5": 150.0, "check": 25.0,
             "a6": 180.0, "repair": 140.0, "fallback": 30.0, "publish": 15.0}
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
        for s in self.extra:                  # a repair runs before the improver, the fallback replaces it
            o.insert(o.index("a6"), s)
        return o

    def enter(self, step: str) -> None:
        if step == self.step or step not in DEFAULT_S:
            return
        now = self.clock()
        self.spent[self.step] = self.spent.get(self.step, 0.0) + now - self.step_t
        if step in ("repair", "fallback") and step not in self.extra:
            self.extra.append(step)
        if step == "fallback" and "a6" in self.order():       # no improver after a fallback page
            self.est["a6"] = 0.0
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
         "codestral-latest": "Codestral", "mistral-medium-latest": "Mistral Medium",
         "deepseek/deepseek-chat": "DeepSeek (test)", "deepseek/deepseek-vision": "DeepSeek vision (test)"}
# The models each step was tuned on (the user's verdicts on R0 / cycle 1, 2026-11-26). Any other model that answers is
# a backup: the Studio says so, so a plainer or rougher page is not a surprise.
PRIMARY = {"a1": {"gemini-3.6-flash", "gemini-4-hydrogen", "gemini-3.8-flash"},
           "a2": {"openai/gpt-oss-120b", "inclusionai/ling-3.2-flash:free"},
           "a3": {"openai/gpt-oss-120b", "inclusionai/ling-3.2-flash:free"},
           "a4": {"qwen/qwen3.8-27b", "openai/gpt-oss-120b", "inclusionai/ling-3.2-flash:free"},
           "a5": {"nvidia/nemotron-3-ultra-550b-a55b:free", "gemini-4-hydrogen", "gemini-3.8-flash"},
           "a6": {"gemini-3.6-flash", "gemini-4-hydrogen", "gemini-3.8-flash"}}
STEP_SHORT = {"a1": "the design brief", "a2": "the layout plan", "a3": "the copy", "a4": "the decoration",
              "a5": "the page", "a6": "the final polish"}


def is_backup(agent: str | None, model: str | None) -> bool:
    if (model or "").startswith("deepseek/"):      # DeepSeek leads A1 and A6 on its accounts (the user's call, 11-27)
        return agent not in ("a1", "a6")
    m = (model or "").removeprefix("openrouter/")
    return bool(agent in PRIMARY and m and m not in PRIMARY[agent])


STEP_TEXT = {"a1": "Reading the reference images", "a2": "Planning the layout", "a3": "Writing the copy",
             "a4": "Drawing the decoration", "a5": "Composing the page", "check": "Checking the page in a browser",
             "a6": "Improving the page by eye", "repair": "Fixing a page that didn't render",
             "fallback": "Building the backup page"}


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
        line = f"{base} · {was} {ev.get('after') or 'is busy'}, switched to {name}" if was and was != name \
            else f"{base} · {name}"
        if is_backup(agent, ev.get("model")):
            line += f" (a backup model: {STEP_SHORT.get(agent, 'this part')} may come out below the usual standard)"
        return line
    if k == "done" and ev.get("source") in ("model", "repaired") and ev.get("ms"):
        return f"{STEP_TEXT.get(agent, agent)} · done by {model_name(ev.get('model'))} in {ev['ms'] / 1000:.0f} s"
    if k == "done" and ev.get("source") == "default":
        return (f"{STEP_TEXT.get(agent, agent)} · no model was free, so a simpler built-in version is used: "
                f"this page will be plainer than usual")
    if k == "done" and agent == "a6" and ev.get("source") in ("failed", "rejected"):
        return ("Improving the page · the improver was unavailable, so you see the composer's page without the "
                "final polish")
    if k == "retry":
        why = {"truncated": "ran out of room, retrying with more", "timeout": "is slow, asking once more"}
        return f"{STEP_TEXT.get(agent, agent)} · {model_name(ev.get('model'))} {why.get(ev.get('why'), 'retrying')}"
    if k == "wait":
        return (f"{STEP_TEXT.get(agent, agent)} · every model is busy right now; waiting {ev.get('s', 0):.0f} s and "
                f"asking again ({ev.get('round', 1)} of 3), never a canned shortcut")
    if k == "check":
        return STEP_TEXT["check"]
    return None


def quality_notes(trace: list[dict]) -> list[str]:
    """One line per step that ran below its usual standard (a backup model, the built-in default, no polish)."""
    out, seen = [], set()
    for t in trace or []:
        ag, src = t.get("agent"), t.get("source")
        if ag in seen:
            continue
        if src == "default":
            out.append(f"{STEP_SHORT.get(ag, ag)}: built-in default (no model was free)")
        elif ag == "a6" and src == "failed":
            out.append("the final polish: skipped (the improver was unavailable)")
        elif src in ("model", "repaired", "salvaged") and is_backup(ag, t.get("model")):
            out.append(f"{STEP_SHORT.get(ag, ag)}: backup model {model_name(t.get('model'))}")
        else:
            continue
        seen.add(ag)
    return out
