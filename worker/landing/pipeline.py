"""pipeline.py - run the five agents over a handoff and write the landing page.

    run(handoff, enabled=True|False, force_from=None, out_dir=..., qa=True) -> result

The agents write one design document together (state.py): A1 (a vision model on OpenRouter - Nemotron VL / Gemma -
sees the five reference images at high detail, each after its role header) describes the whole visual system in
words, A2 plans the layout, A3 writes the copy, A4 draws the decorations (A2-A4 on Groq, Mistral as their backup),
and A5 (a large long-context model on OpenRouter, text only) composes the page from the merged document with real
design freedom. Mistral's free models, then Gemini, are A1 / A5's fallbacks.

Per agent: build its slice (state.slice_for; Groq slices are trimmed to fit the minute window) -> cache lookup ->
route through its model chain (ledger + buckets decide; quota/rate/size errors move to the next model) -> strict
schema + consistency checks -> one repair call -> else its deterministic default. Code normalizes each section
(flow.py) and logs every change.

The gate after A5 discards only broken pages:
  blocking   unsafe / foreign markup, missing copy or hooks, not one h1, text over text, horizontal overflow
  fixed      decoration painted over text or an image is removed; a missing backdrop is injected
  advisory   dead space, hero balance, canvas coverage, gaps, wordmark, ... -> sent back to A5 once
The best candidate without blocking problems ships (a5-1.html, a5-2.html are kept); else compile_spec renders the
same document deterministically (flow.fallback), else the safe spec. result.page_source says which path shipped.
`enabled=False` = no model calls at all.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import jsonschema

from .handoff import font_info
from . import budget, cache, compile_spec, defaults, flow, keys, qa as QA, schemas as sc, state as S, validate_page
from .providers import (DS_PREFIX, MODAL_PREFIX, DeepSeek, Gemini, Groq, Mistral, Modal, OpenRouter, ProviderError,
                        deepseek_base, image_part, image_part_or, modal_base)

PROMPTS = Path(__file__).resolve().parents[2] / "contracts" / "prompts" / "agents"
OUT = Path(os.getenv("LANDING_OUT", r"D:\serpman-studio\out\_landing"))
# Short, explicit chains of comparable models (no lite / small fallbacks). Mistral is the primary for the two
# Gemini-shaped jobs (A1 sees the five references, A5 composes the page) and the backup for Groq's A2-A4; Gemini is
# only the last fallback for A1 / A5 (it was overloaded too often on the free tier). Aliases are checked against the
# key's live model list; "mistral:vision" keeps only models whose capabilities say vision.
# Mistral free tier (measured 2026-11-21): Medium answers "limit 0" on the user's workspace, so the models that run are
# Ministral 14B (vision) for A1, Codestral (HTML/CSS) for A5 and Ministral 8B as Groq's backup: each has its own
# 2 req/min, 40K tok/min pool, so the three jobs never queue behind each other. Medium stays first in case the plan
# opens it; a model the tier refuses is skipped for that key for 6 h (keys.mark_unavailable), the key is kept.
# OpenRouter (2026-11-22, the user's call after Ministral 14B / Codestral produced generic documents and pages): A1 runs
# on a strong vision model with structured outputs, A5 on a large long-context model; both chains are checked against
# OpenRouter's live model list (renamed or retired ids drop out) and its capability data ("openrouter:vision" keeps
# image-capable models with structured outputs, "openrouter:compose" models whose output cap fits A5's page).
# A1 = Ling 3.2 Flash (the user's pick 2026-11-22 after comparing raw A1 documents on the same five references):
# richest per-image description, thinking off. Nemotron VL and the Gemmas stay as fallbacks.
PREFS = {"openrouter:vision": ["inclusionai/ling-3.2-flash:free"],
         # A1's second OpenRouter pick, behind Gemini 3.6 Flash (measured 2026-11-22 on the real A1 request: 3.6
         # Flash 66 s, Ling 75 s, Nemotron VL out of output at 9K tokens after 59 s, ~90 s once retried)
         "openrouter:vision-alt": ["nvidia/nemotron-3.5-super-vl:free"],
         # A5 = Nemotron 3 Ultra 550B (the user's pick 2026-11-22, after comparing raw A5 pages on one A1-A4 spec);
         # Nemotron VL behind it. Gemma 4 left OpenRouter (its free endpoints are rate-limited upstream for every
         # account, 2026-11-22): it runs on the user's own Gemini keys instead ("gemini:gemma")
         "openrouter:compose": ["nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-3.5-super-vl:free"],
         # Mistral: off every chain since 2026-11-26 (HTTP 402, the free tier needs a subscription); kept for tests
         "mistral:vision": ["mistral-medium-latest", "ministral-14b-latest"],
         "mistral:compose": ["mistral-medium-latest", "codestral-latest", "ministral-14b-latest"],
         "mistral:text": ["mistral-medium-latest", "ministral-8b-latest", "ministral-14b-latest"],
         # A2-A4: Ling only; Nemotron VL ran out of output on all three text agents (2026-11-22), the user removed it
         "openrouter:text": ["inclusionai/ling-3.2-flash:free"],
         "gemini": ["gemini-4-hydrogen", "gemini-3.8-flash"],
         "gemini:flash": ["gemini-3.6-flash"],
         # Gemma 4 on the Gemini API with the user's own Gemini keys: its own quota, not OpenRouter's shared pool.
         # Images and strict JSON work; thinkingLevel is rejected (providers.Gemini leaves it out for gemma)
         "gemini:gemma": ["gemma-4-31b-it", "gemma-4-26b-a4b-it"],
         # the user's own GPU endpoint (deploy/modal_vlm.py); used only when MODAL_BASE + MODAL_API_KEY are set
         "modal": [os.getenv("MODAL_MODEL", "Qwen/Qwen3-VL-30B-A3B-Instruct-FP8")],
         # DeepSeek (test arm only: the local FreeDeepseekAPI proxy; providers.deepseek_base gates it)
         "deepseek:text": ["deepseek-chat"],
         "deepseek:vision": ["deepseek-vision"],
         "groq:big": ["openai/gpt-oss-120b"],
         "groq:vision": ["qwen/qwen3.8-27b"],
         # free OpenRouter models that were never on the text agents' chains (cycle 1, 2026-11-26: every A2-A4 fallback
         # had only Ling (upstream-limited for everyone), Groq (request larger than its 8K/min window) and Mistral
         # (402: the free tier now needs a subscription) to try - no key can fix any of those)
         "openrouter:text-alt": ["nvidia/nemotron-3-ultra-550b-a55b:free", "nvidia/nemotron-3.5-lightning:free"],
         "openrouter:compose-alt": ["nvidia/nemotron-3.5-lightning:free"],
         # a further vision model with structured outputs for A1 (free; never tried before 2026-11-26)
         "openrouter:vision-extra": ["particle-ai/particle-1:free"]}
# A1 order (the user's R0 notes, 2026-11-26): Gemini 3.6 Flash wrote the best design documents of the last 5 builds
# (10 sections, every colour traced); Nemotron VL's were ~30% thinner and mislabelled section roles. Hydrogen / 3.8
# never answered in those builds; keys.health_* skips a model that keeps failing, so they cost little where they stand.
# A6 = the improver (the user's P1): a vision model that sees A5's rendered page and returns the improved page.
# Priority (the user's calls, 2026-11-22): A1 / A5 on the user's picks first (Gemini, then Ling for A1 / Nemotron
# Ultra for A5). A1: then Gemini 3.6 Flash (faster than Nemotron VL there), Nemotron VL; A5: then Nemotron VL, 3.6 Flash
# (it ran out of output at 20K tokens on the real A5 request, Ultra finished in 177 s). Then Gemma 4 on the user's
# Gemini keys, the user's Modal GPU (only when configured), Mistral last. A2-A4: Ling, then Groq, Mistral last.
CHAINS = {"a1": ["gemini:flash", "gemini", "openrouter:vision-alt", "openrouter:vision", "openrouter:vision-extra",
                 "gemini:gemma", "modal"],
          # A6 without Nemotron VL (the user's verdict on cycle 1, 2026-11-26: its rewrites drew crude shapes and made
          # text less readable; the one improved page the user liked was Gemini 3.6 Flash's). No improver -> A5's page
          # ships and the Studio says the final polish was skipped.
          "a6": ["gemini:flash", "gemini", "openrouter:vision", "gemini:gemma", "modal"],
          "a2": ["openrouter:text", "groq:big", "gemini:flash", "openrouter:text-alt", "gemini:gemma", "gemini"],
          "a3": ["openrouter:text", "groq:big", "gemini:flash", "openrouter:text-alt", "gemini:gemma", "gemini"],
          "a4": ["openrouter:text", "groq:vision", "groq:big", "gemini:flash", "openrouter:text-alt", "gemini:gemma",
                 "gemini"],
          "a5": ["gemini", "openrouter:compose", "openrouter:vision", "gemini:flash", "openrouter:compose-alt",
                 "gemini:gemma", "modal"]}
# No deterministic fallbacks (the user's call, 2026-11-26): when every model of a chain is out, the agent waits and
# asks the whole chain again (cooldowns ignored; daily limits and rejected keys still count) after each of these
# pauses; if no model answers even then, the job fails with an honest message and nothing canned is published.
# LANDING_NO_DEFAULTS=0 restores the old code defaults / compile_spec page (tests, the lab, agents-off runs always
# use them: enabled=False is the deterministic mode by definition).
RETRY_WAITS = (45.0, 90.0, 180.0)


def no_defaults() -> bool:
    return os.getenv("LANDING_NO_DEFAULTS", "1") != "0"


class AgentUnavailable(RuntimeError):
    """No model could do an agent's work even after the retry rounds: the job fails rather than ship canned content."""
    def __init__(self, agent: str, tried: list, detail: str = ""):
        step = {"a1": "design brief", "a2": "layout plan", "a3": "copy", "a4": "decoration", "a5": "page"}.get(agent, agent)
        kinds = sorted({why_left(t) for t in tried if t.get("model")})
        super().__init__(f"No AI model could write the {step} right now ({', '.join(kinds[:4]) or 'all busy'}), even "
                         f"after waiting {int(sum(RETRY_WAITS))} s. Nothing was published; please try again in a few "
                         f"minutes." + (f" [{detail[:200]}]" if detail else ""))
        self.agent, self.tried = agent, tried
# A4 is text-only (A1 describes the images); Qwen keeps its own minute window apart from A2/A3's gpt-oss.
# If every model of a chain is out, the agent falls back to code (the default document / compile_spec).
MISTRAL_PREFIXES = ("mistral", "ministral", "magistral", "pixtral", "devstral", "codestral")
A1_SIDE = {"high": 1540, "medium": 1024, "low": 1024}   # Mistral: <=1540 px, ~(W*H)/784 tokens per image
OR_SIDE = {"high": 1536, "medium": 1280, "low": 1024}   # OpenRouter vision models, JPEG q90, detail "high"; 1024-1536 px keeps fine text crisp without oversized payloads
# A3 4800 (11-28): with A1's depth floor the copy covers more components; Gemini 3.6 Flash ran out at 3000 / 4800
MAX_OUT = {"a1": 23040,"a2": 3000, "a3": 4800, "a4": 4000, "a5": 20000, "a6": 26000}
# what a Groq minute window keeps free for the reply (its usual size, not the cap): a bigger cap for the other providers
# must not shrink the room Groq's request has
GROQ_RESERVE = {"a2": 1800, "a3": 1800, "a4": 2400}
GROQ_MAX_OUT = {"a3": 3000}            # Groq counts the requested output against its minute window
# free OpenRouter models reason before they answer (Nemotron Ultra / Lightning ran out at 3000 / 4800 on A2, 11-28);
# the free pool counts requests, not tokens
OPENROUTER_MIN_OUT = {"a2": 7200, "a3": 7200, "a4": 7200}
TEMP = {"a1": 0.5, "a2": 0.4, "a3": 0.6, "a4": 0.7, "a5": 0.7, "a6": 0.5}
THINK = {"a1": "medium", "a5": "medium"}            # Gemini thinking level per agent (others: low)
A1_RES = {"LAYOUT_REF": "high", "TYPOGRAPHY_REF": "high", "ELEMENTS_REF": "medium", "BACKGROUND_REF": "medium",
          "PALETTE_REF": "low"}
WAIT_MAX = 20.0                         # longer waits for a minute window -> try the next model instead
WAIT_MAX_MISTRAL = 65.0                 # Mistral's free tier is 2 req/min: waiting out the minute is normal there
# Gemini gets short limits of its own: it answers fast or not at all, and the next model in line takes over
GEMINI_TIMEOUT = {"a1": 60.0, "a2": 25.0, "a3": 25.0, "a4": 25.0, "a5": 75.0, "a6": 90.0}
# OpenRouter's free models are slow but good (Ling ~150-220 s on A1 and ~100 s on A3, Nemotron Ultra ~140-200 s on A5)
OPENROUTER_TIMEOUT = {"a1": 240.0, "a2": 120.0, "a3": 120.0, "a4": 120.0, "a5": 240.0, "a6": 360.0}
GEMINI_SKIP_S = 600.0                   # a Gemini model that was busy / timed out is skipped this long, on every key
# the quick give-up above is for Hydrogen / 3.8 Flash (overloaded: a fast failure beats a slow one); 3.6 Flash and
# Gemma on the Gemini keys are fallbacks that are slow but answer (3.6 Flash: 66 s on the real A1 request)
GEMINI_PATIENT = {"a1": 150.0, "a2": 60.0, "a3": 90.0, "a4": 60.0, "a5": 300.0, "a6": 360.0}
UPSTREAM_SKIP_S = 300.0                 # an OpenRouter free model rate-limited upstream: skipped this long, on every key
MODAL_TIMEOUT = {"a1": 600.0, "a2": 300.0, "a3": 300.0, "a4": 300.0, "a5": 600.0, "a6": 600.0}   # per read: covers a cold boot
TIMEOUT = {"a1": 100.0, "a2": 30.0, "a3": 30.0, "a4": 30.0, "a5": 100.0, "a6": 300.0}
STICKY_S = 600.0                       # after a switch to the alternate, stay on it this long before retrying the primary
ORDER = ["a1", "a2", "a3", "a4", "a5", "a6"]
SHOT_TILE = {"desktop": (1100, 5), "phone": (844, 2)}    # screenshot tiles for the improver: height px, how many


def prompt(name: str) -> str:
    """An agent's system prompt; an '<agent>_example.json' next to it is appended as the depth expected."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    ex = PROMPTS / f"{name}_example.json"
    if ex.exists():
        text += ("\n\nTHE DEPTH EXPECTED - a design document written for a DIFFERENT brand from DIFFERENT references. "
                 "Match its level of observed detail (named colours with exact uses, element geometry, positions, "
                 "layers, overlap reasons); never reuse its subjects, copy, colours or fonts, and answer in the schema "
                 "you are given, not in this example's keys:\n" + ex.read_text(encoding="utf-8"))
    return text


class NoModel(RuntimeError):
    def __init__(self, msg: str, tried: list | None = None):
        super().__init__(msg)
        self.tried = tried or []


class Ctx:
    def __init__(self, enabled: bool, log=print, progress=None):
        self.enabled, self.log = enabled, log
        self.progress = progress or (lambda ev: None)    # {kind: start / try / done / check / finish, agent, model}
        self.buckets, self.ledger = budget.Buckets(), budget.Ledger()
        self.gemini, self.groq, self.mistral = Gemini(), Groq(self.buckets), Mistral(self.buckets)
        self.openrouter, self.modal = OpenRouter(self.buckets), Modal(self.buckets)
        self.deepseek = DeepSeek(self.buckets)
        self.rings = {p: keys.Ring(p if enabled else "") for p in ("openrouter", "mistral", "groq", "gemini", "modal",
                                                                   "deepseek")}
        self.resolved: dict[str, list[str]] = {}

    @staticmethod
    def pname(model: str) -> str:
        if model.startswith(MODAL_PREFIX):
            return "modal"
        if model.startswith(DS_PREFIX):
            return "deepseek"
        if model.startswith(budget.OR_PREFIX):
            return "openrouter"
        if model.startswith(("gemini", "gemma")):
            return "gemini"
        return "mistral" if model.startswith(MISTRAL_PREFIXES) else "groq"

    def resolve(self, alias: str) -> list[str]:
        """Alias -> its preferred models that this provider lists (checked with the first key that works)."""
        if alias not in self.resolved and alias.split(":", 1)[0] == "deepseek":   # the local test proxy: trust the config
            self.resolved[alias] = [DS_PREFIX + m for m in PREFS[alias]] if deepseek_base() and len(self.rings["deepseek"]) else []
        if alias not in self.resolved and alias.split(":", 1)[0] == "modal":   # listing would boot the GPU: trust the config
            self.resolved[alias] = [MODAL_PREFIX + m for m in PREFS[alias]] if modal_base() and len(self.rings["modal"]) else []
        if alias not in self.resolved:
            name = alias.split(":", 1)[0]
            ring, prov = self.rings[name], self.provider(name)
            picks: list[str] = []
            for i in range(len(ring)):
                if i in ring.disabled:
                    continue
                try:
                    if name == "openrouter":
                        self._openrouter_key(ring, i)
                    live = set(prov.models(ring.keys[i]))
                    picks = [m for m in PREFS[alias] if m in live]
                    if alias == "mistral:vision":
                        picks = [m for m in picks if prov.vision(m)]
                    if alias.startswith("openrouter:vision"):
                        picks = [m for m in picks if prov.vision(m) and prov.structured(m)]
                    if alias == "openrouter:compose":      # no stated cap: keep it and let the reply decide
                        picks = [m for m in picks if (prov.caps(m).get("max_out") or MAX_OUT["a5"]) >= MAX_OUT["a5"]]
                    break
                except ProviderError as e:
                    if e.kind == "auth":
                        ring.disable(i, str(e))
                        keys.notify(f"{ring.label(i)} was rejected ({str(e)[:80]}); skipping it this session")
                        continue
                    picks = list(PREFS[alias])             # can't list: try the preferences, let errors decide
                    break
            if name == "openrouter":
                picks = [budget.OR_PREFIX + m for m in picks]
            self.resolved[alias] = picks
        return self.resolved[alias]

    def provider(self, name: str):
        return {"gemini": self.gemini, "groq": self.groq, "mistral": self.mistral, "openrouter": self.openrouter,
                "modal": self.modal, "deepseek": self.deepseek}[name]

    def _openrouter_key(self, ring, i: int) -> None:
        """Check an OpenRouter key once (a bad key raises 'auth') and adopt the account's free daily pool and how much
        of it is used today (other apps on the same account count too)."""
        info = self.openrouter.key_info(ring.keys[i])
        budget.set_free_daily(info.get("free_limit"))
        if isinstance(info.get("free_used"), int):
            self.ledger.sync(budget.OR_FREE_POOL, info["free_used"], ring.ids[i])

    def chain(self, agent: str, arm: bool = False) -> list[str]:
        pinned = os.getenv(f"AGENT{agent[1]}_MODEL", "").strip()
        if pinned:
            return [m.strip() for m in pinned.split(",") if m.strip()]
        # DeepSeek test arm (the user's call, 2026-11-26): it leads A1 and the improver (A6) only. It never runs A5 -
        # not its page, not its repair - nor A2-A4.
        lead = ["deepseek:vision"] if deepseek_base() and agent in ("a1", "a6") else []
        base = list(dict.fromkeys(m for a in lead + CHAINS.get(agent, []) for m in self.resolve(a)))
        pick = _PREFERRED.get(tuple(base))               # sticky: the model that last answered for this chain
        if pick and pick[0] in base and (pick[0] == base[0] or time.monotonic() - pick[1] < STICKY_S):
            base.remove(pick[0])
            base.insert(0, pick[0])
        return base

    def describe(self) -> str:
        return "; ".join(f"{a.upper()} {' -> '.join(self.chain(a)) or 'no model'}" for a in ORDER)

    def ring_left(self, model: str) -> bool:
        return bool(self.rings[self.pname(model)].order(model, self.ledger))

    def quota(self, models) -> dict:
        return {m: self.ledger.left_total(m, self.rings[self.pname(m)].ids) for m in models}


# --------------------------------------------------------------------------- one model call with routing
# process-wide (kept across the lab's hot reloads): the model that last answered for each chain (sticky choice,
# so A1, A5 and repairs stay on one model), and (model, agent) pairs whose constrained JSON failed (plain JSON mode).
_PREFERRED: dict[tuple, tuple[str, float]] = globals().get("_PREFERRED", {})
_NONSTRICT: set[tuple[str, str]] = globals().get("_NONSTRICT", set())
MINUTE_WAIT_MAX = 65.0
LOCAL_RATE = "this key's minute window is full"   # the router's own pre-check (budget.Buckets), not a provider 429                  # when every key/model is only in its minute window: wait once, up to this


def why_left(t: dict) -> str:
    """A tried-model record -> a few plain words for the Studio ("timed out", "is overloaded", ...)."""
    w = (t.get("error") or t.get("skip") or "").lower()
    for key, words in (("timeout", "timed out"), ("overloaded", "is overloaded"), ("503", "is overloaded"),
                       ("upstream", "is rate-limited"), ("truncat", "ran out of output"),
                       ("times in a row", "keeps failing today"), ("per-minute", "is at its per-minute limit"),
                       ("minute window", "is at its per-minute limit"), ("daily", "is out for today"),
                       ("tier", "isn't on this plan"), ("402", "needs a paid plan"), ("subscription", "needs a paid plan"),
                       ("too_large", "can't take a request this size"), ("no api key", "has no key")):
        if key in w:
            return words
    return "is busy"


def call(ctx: Ctx, agent: str, build, max_out: int, skip=None, fresh: bool = False,
         arm: bool = False) -> tuple[dict | str, str, dict, list]:
    """build(model) -> ("gemini", system, parts, schema) | ("groq" | "mistral", messages, schema, est_tokens).
    For each model in the agent's chain (the model that last answered for this chain goes first), each usable
    key in order: a daily limit marks that key out for the model (ledger), a per-minute limit cools the key and moves
    to the next one, a rejected key is skipped for the session. If every attempt failed only because of minute
    windows, wait once for the first window to reopen and go round again. Every switch prints one line on the
    terminal (keys.notify). -> (parsed output or text, model, reply meta incl. key label, tried[])."""
    tried = []
    chain = [m for m in ctx.chain(agent, arm) if not skip or m not in skip] or ctx.chain(agent, arm)
    stick = tuple(dict.fromkeys(m for a in CHAINS.get(agent, []) for m in ctx.resolve(a)))

    def after(model):
        rest = chain[chain.index(model) + 1:]
        return f"trying {rest[0]}" if rest else "no model left (the agent uses its default)"

    for rnd in range(2):
        minute_only = True
        for model in chain:
            ring = ctx.rings[ctx.pname(model)]
            if not len(ring):
                tried.append({"model": model, "skip": "no API key"})
                minute_only = False
                continue
            order = ring.order(model, ctx.ledger)
            if not order:
                off_tier = all(ring.unavailable(i, model) for i in range(len(ring)) if i not in ring.disabled)
                tried.append({"model": model, "skip": f"not on the tier of any {ring.provider} key" if off_tier else
                              f"all {len(ring)} {ring.provider} key(s) are out for today or rejected"})
                minute_only = False
                continue
            left, rec = keys.health_skip(model)
            if left and not fresh:
                tried.append({"model": model, "skip": f"failed {rec.get('fails')} times in a row "
                                                      f"({rec.get('why', '')[:60]}); skipped for {left / 60:.0f} more min"})
                minute_only = False
                continue
            ctx.progress({"kind": "try", "agent": agent, "model": model, "rank": chain.index(model),
                          "after": why_left(tried[-1]) if tried else None})
            req = build(model)
            next_model = False
            for n, i in enumerate(order):
                key, kid, label = ring.keys[i], ring.ids[i], ring.label(i)
                later = order[n + 1:]
                nxt = ring.label(later[0]) if later else None
                cool = 0.0 if fresh else ring.cooling_for(i, model)   # sorted by cooldown: if this one cools, all do
                if cool > WAIT_MAX:
                    tried.append({"model": model, "key": label, "skip": f"per-minute limit, cooling {cool:.0f}s"})
                    break
                if cool:
                    keys.notify(f"{label} is cooling down on {model}: waiting {cool:.0f}s")
                    time.sleep(cool)
                pk = ctx.pname(model)
                out_cap, t_key = (min(max_out, GROQ_MAX_OUT.get(agent, max_out)) if pk == "groq" else
                                  max(max_out, OPENROUTER_MIN_OUT.get(agent, 0)) if pk == "openrouter" else
                                  max_out), time.time()
                strict = (model, agent) not in _NONSTRICT
                for attempt in range(3):
                    try:
                        if req[0] == "gemini":
                            _, system, parts, schema = req
                            est = budget.est_text(system + "".join(p.get("text", "") for p in parts)) + sum(
                                budget.GEMINI_IMAGE.get(p.get("res", "high"), 1120) for p in parts if "image" in p) + (
                                budget.est_text(json.dumps(schema, separators=(",", ":"))) if schema else 0)
                            reply = ctx.gemini.generate(model, system, parts, key=key, schema=schema, max_out=out_cap,
                                                        temperature=TEMP[agent],
                                                        timeout=(GEMINI_TIMEOUT if model in PREFS["gemini"]
                                                                 else GEMINI_PATIENT)[agent],
                                                        thinking=THINK.get(agent, "low"))
                        else:
                            kind, messages, schema, est = req
                            prov = ctx.provider(kind)
                            if not strict and schema is not None:   # the schema rides in the prompt in plain mode
                                est += budget.est_text(json.dumps(sc.inline_refs(sc.provider_schema(schema)),
                                                                  separators=(",", ":")))
                            wait = ctx.buckets.wait_for(model, est + int(out_cap * 0.6), kid)
                            wmax = WAIT_MAX_MISTRAL if kind == "mistral" else WAIT_MAX
                            if wait == float("inf"):
                                raise ProviderError("too_large", f"~{est} tokens won't fit {model}'s minute window")
                            if wait > wmax or (wait > 3 and later):   # checked here, before any request is sent
                                raise ProviderError("rate", f"{LOCAL_RATE} for {wait:.0f}s", wait)
                            if wait:
                                ctx.log(f"  {agent}: waiting {wait:.1f}s for {model}'s token window ({label})")
                                time.sleep(wait)
                            reply = prov.chat(model, messages, key=key, kid=kid, schema=schema, name=agent,
                                                  max_out=out_cap, temperature=TEMP[agent], strict=strict,
                                                  timeout=(OPENROUTER_TIMEOUT if kind == "openrouter" else
                                                           MODAL_TIMEOUT if kind == "modal" else
                                                           OPENROUTER_TIMEOUT if kind == "deepseek" else TIMEOUT)[agent])
                        u = reply.usage
                        ctx.ledger.record(model, u.get("in", 0) + u.get("out", 0) + u.get("thinking", 0), kid)
                        ctx.buckets.note(model, max(0, u.get("in", 0) - u.get("cached", 0)) + u.get("out", 0)
                                         + u.get("thinking", 0), kid)
                        data = reply.json() if (req[0] == "gemini" and req[3] is not None) or \
                            (req[0] != "gemini" and req[2] is not None) else reply.text
                        keys.health_ok(model)
                        if model != (_PREFERRED.get(stick) or ("",))[0]:
                            _PREFERRED[stick] = (model, time.monotonic())
                        return data, model, {"ms": reply.ms, "usage": u, "headers": reply.headers, "key": label,
                                             "est_in": est, "strict": strict}, tried
                    except ProviderError as e:
                        if e.kind == "truncated" and attempt == 0:
                            keys.notify(f"{agent.upper()}: {model} ran out of output at {out_cap} tokens after "
                                        f"{time.time() - t_key:.0f}s; retrying once with {int(out_cap * 1.6)}")
                            ctx.progress({"kind": "retry", "agent": agent, "model": model, "why": "truncated"})
                            out_cap = int(out_cap * 1.6)
                            continue
                        if e.kind == "bad_output" and req[0] != "gemini" and strict:
                            _NONSTRICT.add((model, agent))
                            keys.notify(f"{agent.upper()}: {model}'s constrained JSON failed; using plain JSON mode "
                                        f"(checked locally) for it from now on")
                            strict = False
                            continue
                        if e.kind == "unavailable":     # the tier doesn't offer this model: not a key problem
                            ring.mark_unavailable(i, model, str(e))
                            keys.notify(f"{label}: {str(e)[13:120]} -> " + (f"using {nxt}" if nxt else after(model))
                                        )
                            tried.append({"model": model, "key": label, "skip": "not on this key's tier"})
                            minute_only = False
                            break
                        if e.kind == "upstream":           # the free model's host is full for everyone: no key helps
                            for j in range(len(ring)):
                                ring.cool_down(j, model, UPSTREAM_SKIP_S)
                            if sk := keys.health_fail(model, "rate-limited upstream", slow=False):
                                keys.notify(f"{model} failed {keys.HEALTH_STRIKES} times in a row: skipped for "
                                            f"{sk / 60:.0f} min")
                            tried.append({"model": model, "key": label, "error": "rate-limited upstream"})
                            keys.notify(f"{agent.upper()}: {model} is rate-limited upstream (shared free capacity, every "
                                        f"key) -> {after(model)}")
                            minute_only = False
                            next_model = True
                            break
                        if e.kind == "rate":
                            ring.cool_down(i, model, e.retry_after or 60)
                            local = LOCAL_RATE in str(e)
                            what = (f"would exceed its per-minute window on {model} for {e.retry_after:.0f}s "
                                    f"(counted locally, no request sent)") if local else \
                                f"hit the per-minute limit on {model}"
                            if nxt:
                                keys.notify(f"{label} {what} -> using {nxt}")
                                tried.append({"model": model, "key": label, "error": "per-minute limit"})
                                break
                            if e.retry_after and e.retry_after <= (WAIT_MAX_MISTRAL if req[0] == "mistral"
                                                                    else WAIT_MAX) and attempt == 0:
                                keys.notify(f"{label} hit the per-minute limit on {model}; waiting {e.retry_after:.0f}s "
                                            f"(no other key free)")
                                time.sleep(e.retry_after)
                                continue
                            keys.notify(f"{label} hit the per-minute limit on {model}; no other key free -> "
                                        f"{after(model)}")
                            tried.append({"model": model, "key": label, "error": str(e)[:200]})
                            next_model = True
                            break
                        minute_only = False
                        if e.kind == "quota_day":
                            ctx.ledger.exhaust(model, str(e), kid)
                            keys.notify(f"{label} reached its daily limit for {model} (resets at midnight Pacific)"
                                        + (f" -> using {nxt}" if nxt else f" -> no {ring.provider} key left for this model"))
                            tried.append({"model": model, "key": label, "error": "daily limit"})
                            break
                        if e.kind == "auth":
                            ring.disable(i, str(e))
                            keys.notify(f"{label} was rejected ({str(e)[:80]}); skipping it this session"
                                        + (f" -> using {nxt}" if nxt else ""))
                            tried.append({"model": model, "key": label, "error": "key rejected"})
                            break
                        if req[0] == "gemini" and e.kind in ("overloaded", "timeout", "server"):
                            for j in range(len(ring)):                # Google-side trouble: every key, for a while
                                ring.cool_down(j, model, GEMINI_SKIP_S)
                            if sk := keys.health_fail(model, f"{e.kind}: {str(e)[:80]}", slow=e.kind == "timeout"):
                                keys.notify(f"{model} failed {keys.HEALTH_STRIKES} times in a row: skipped for "
                                            f"{sk / 60:.0f} min")
                            tried.append({"model": model, "key": label, "error": str(e)[:240],
                                          "s": round(time.time() - t_key, 1)})
                            keys.notify(f"{agent.upper()}: {model} {e.kind} ({str(e)[:90]}) -> {after(model)}; "
                                        "retried on the next call")
                            next_model = True
                            break
                        if e.kind == "timeout" and attempt == 0:   # slow is not broken: once more, same model
                            ctx.progress({"kind": "retry", "agent": agent, "model": model, "why": "timeout"})
                            keys.notify(f"{agent.upper()}: {model} took over "
                                        f"{(OPENROUTER_TIMEOUT if req[0] == 'openrouter' else TIMEOUT)[agent]:.0f}s; "
                                        f"retrying it once")
                            continue
                        tried.append({"model": model, "key": label, "error": str(e)[:240],  # not a key problem
                                      "s": round(time.time() - t_key, 1)})
                        keys.notify(f"{agent.upper()}: {model} {e.kind} ({str(e)[:110]}) -> {after(model)}")
                        next_model = True
                        break
                if next_model:
                    break
        if rnd == 0 and minute_only and tried:
            waits = [ctx.rings[ctx.pname(m)].cooling_for(i, m) for m in chain
                     for i in range(len(ctx.rings[ctx.pname(m)]))]
            w = min([x for x in waits if x > 0] or [0.0])
            if 0 < w <= MINUTE_WAIT_MAX:
                keys.notify(f"{agent.upper()}: every key is inside its per-minute window; waiting {w:.0f}s, then one "
                            f"more round")
                time.sleep(w)
                continue
        break
    raise NoModel("; ".join(f"{t['model']}{' ' + t['key'] if t.get('key') else ''}: {t.get('skip') or t.get('error')}"
                            for t in tried) or "no model", tried)


# --------------------------------------------------------------------------- agents
def semantic(agent: str, out: dict) -> list[str]:
    """Consistency checks a schema can't express. They never ask for a particular design."""
    errs = []
    if agent == "a1":
        if not (out.get("query_context") or "").strip():
            errs.append("query_context is empty")
        if not out.get("content_sections"):
            errs.append("content_sections is empty: describe the page's sections")
        n = sum(len(v) for v in (out.get("color_palette_distribution") or {}).values())
        if n < 4:
            errs.append(f"color_palette_distribution names only {n} colours; describe the palette you observed")
        ids = [c.get("card_id") for c in out.get("strategic_cards", [])]
        if len(ids) != len(set(ids)):
            errs.append(f"strategic_cards: each card_id once (got {ids})")
        for c in out.get("strategic_cards", []):
            if not c.get("heading", "").strip() or not c.get("body", "").strip():
                errs.append(f"{c.get('card_id')}: heading and body are required")
        dl = out.get("design_language") or {}           # the language every later agent builds with (11-28)
        if len([x for x in dl.get("theory") or [] if str(x).strip()]) < 2:
            errs.append("design_language.theory: give at least 2 principles explaining why the references work")
        if len(dl.get("component_styles") or []) < 3:
            errs.append("design_language.component_styles: style at least 3 components the page uses "
                        "(button, card, image_frame, nav, tag...)")
        if len((dl.get("shape_vocabulary") or {}).get("allowed_shapes") or []) < 2:
            errs.append("design_language.shape_vocabulary.allowed_shapes: name at least 2 shapes this design uses")
    elif agent == "a2":
        if not out.get("layout_plan", {}).get("sections"):
            errs.append("layout_plan.sections is empty")
    elif agent == "a3":
        items = out.get("copy", {}).get("items", [])         # a missing / extra h1 is fixed by code (flow.after_a3)
        if not any((x.get("text") or "").strip() for x in items):
            errs.append("copy.items has no text: write the words of every section")
    elif agent == "a4":
        d = out.get("decor", {})
        if d.get("intent") != "none" and not d.get("assets"):
            errs.append(f"intent is {d.get('intent')!r} but there are no assets")
        for a in d.get("assets", []):
            if a.get("kind") == "svg" and not (a.get("svg") or "").strip().lower().startswith("<svg"):
                errs.append(f"{a.get('element_id')}: kind svg needs one <svg> element in svg")
            if a.get("kind") == "css" and not (a.get("css") or "").strip():
                errs.append(f"{a.get('element_id')}: kind css needs declarations in css")
    return errs


# A3's copy kinds (sc.COPY_KINDS) for the names models also use
KIND_ALIAS = {"heading": "h2", "title": "h2", "subheading": "h3", "subtitle": "h3", "body": "paragraph",
              "text": "paragraph", "intro_body": "paragraph", "intro_heading": "h2", "list": "list_item",
              "tag": "label", "badge": "label", "button": "cta", "link": "nav_link", "wordmark": "logo"}


def lenient(st: S.State, agent: str, out):
    """Before validation, settle values a model gets slightly wrong instead of dropping the agent to its default (a
    Studio job lost A2's whole plan over one missing 'notes', 2026-11-22). Fills blanks and maps synonyms only; never
    invents content."""
    if not isinstance(out, dict):
        return out
    if agent == "a1":
        if not isinstance(out.get("image_slots"), list):       # a page without picture places is a valid answer
            out["image_slots"] = []
        for x in out["image_slots"]:
            if isinstance(x, dict):
                for f in ("slot_id", "section_id", "subject", "style"):
                    x.setdefault(f, "")
                if x.get("aspect") not in sc.ASPECTS:
                    x["aspect"] = "4:3"
    elif agent == "a2":
        lay = S.layer_of(st["doc"]) if st.get("doc") else {}
        for L in (out.get("layout_plan") or {}).get("layers") or []:
            if isinstance(L, dict):
                L.setdefault("notes", "")
                L.setdefault("rotate", 0)
                if not isinstance(L.get("box"), dict):      # no box: placement prose carries it (flow.clean_box -> None)
                    L["box"] = {"x0": 0, "y0": 0, "x1": 0, "y1": 0}
                z = L.get("z")
                if z not in sc.DECOR_Z:                     # e.g. 10 (the text layer): the element's own A1 layer
                    near = z if isinstance(z, (int, float)) else 5
                    L["z"] = lay[L["element_id"]][1] if L.get("element_id") in lay else \
                        min(sc.DECOR_Z, key=lambda v: abs(v - near))
    elif agent == "a3":
        for it in (out.get("copy") or {}).get("items") or []:
            if isinstance(it, dict):
                k = str(it.get("kind", "")).strip().lower()
                if k not in sc.COPY_KINDS:
                    it["kind"] = KIND_ALIAS.get(k, "paragraph")
                for f in ("text", "href", "card_id"):
                    it.setdefault(f, "")
    elif agent == "a4":
        for a in (out.get("decor") or {}).get("assets") or []:
            if isinstance(a, dict):
                for f in ("svg", "css", "anchor", "placement", "notes"):
                    a.setdefault(f, "")
                a.setdefault("opacity", 1)
    return out


SALVAGE = ("a2",)          # agents whose output is kept in part when it fails validation (the user's call, R0)
# A1's depth gate (the user's call, 2026-11-26: "going back to A1 if generation is less than a certain size"). In the
# R0 builds the documents that carried the page were 15-16K characters with 41-47 words per section (Gemini 3.6
# Flash); the thin ones that starved A5 were 10.7-11K with 25-32 (Ministral 14B, Nemotron VL). A document under any
# of these gets one more A1 call on the next vision model, and the deeper of the two is kept.
A1_MIN = {"chars": 12500, "words_per_section": 34, "sections": 5}


def a1_measure(doc) -> dict:
    """How much an A1 document says: its size, sections, words per section's components, elements with geometry."""
    if not isinstance(doc, dict):
        return {"chars": 0, "sections": 0, "words_per_section": 0, "elements": 0, "score": 0.0}
    secs = doc.get("content_sections") or []
    words = sum(len(" ".join(x for x in (s.get("what") or []) if isinstance(x, str)).split()) for s in secs
                if isinstance(s, dict))
    els = (((doc.get("background_layer") or {}).get("elements") or []) + (doc.get("midground_decor") or []) +
           (doc.get("foreground_overlays") or []))
    m = {"chars": len(json.dumps(doc, ensure_ascii=False)), "sections": len(secs),
         "words_per_section": round(words / max(1, len(secs)), 1),
         "elements": sum(1 for e in els if isinstance(e, dict) and len(str(e.get("geometry", ""))) >= 20)}
    m["score"] = round(m["chars"] / 12500 + m["words_per_section"] / 34 + min(m["sections"], 10) / 5
                       + 0.1 * min(m["elements"], 8), 2)        # fixed scale: thresholds may change, ranking doesn't
    return m


def a1_thin(m: dict) -> list[str]:
    return [f"{k} {m[k]} < {v}" for k, v in A1_MIN.items() if m.get(k, 0) < v]


def salvage(st: S.State, agent: str, outs: list) -> dict | None:
    """A2's plan that failed its schema -> the entries that are usable, made valid (later outputs first). Code fills
    the sections and layers it drops from defaults (flow.after_a2), so one bad entry no longer costs the whole plan
    (a Studio job lost 4 good sections over sections[4] = '', 2026-11-23). None when nothing is usable."""
    if agent != "a2":
        return None
    sids, eids, names = flow.a2_enums(st)
    d = st["doc"]
    lay = S.layer_of(d)
    hero = next((s["section_id"] for s in d["content_sections"] if s["role"] == "hero"), sids[0])
    base = d["role_names"]["bg_primary"]
    for out in reversed(outs):
        lp = out.get("layout_plan") if isinstance(out, dict) else None
        if not isinstance(lp, dict):
            continue
        secs, seen = [], set()
        for x in lp.get("sections") or []:
            if isinstance(x, dict) and x.get("section_id") in sids and x["section_id"] not in seen:
                seen.add(x["section_id"])
                secs.append({"section_id": x["section_id"], "layout": str(x.get("layout") or ""),
                             "size": str(x.get("size") or ""), "responsive": str(x.get("responsive") or ""),
                             "surface": x.get("surface") if x.get("surface") in names else base})
        if not secs:
            continue
        layers = []
        for L in lp.get("layers") or []:
            if isinstance(L, dict) and L.get("element_id") in eids:
                z = L.get("z") if L.get("z") in sc.DECOR_Z else lay.get(L["element_id"], ("", 5))[1]
                box = L.get("box") if isinstance(L.get("box"), dict) else {}
                try:
                    box = {k: float(box.get(k, 0)) for k in ("x0", "y0", "x1", "y1")}
                except (TypeError, ValueError):
                    box = {"x0": 0.0, "y0": 0.0, "x1": 0.0, "y1": 0.0}
                rot = L.get("rotate") if isinstance(L.get("rotate"), (int, float)) else 0
                layers.append({"element_id": L["element_id"], "z": z,
                               "anchor": L.get("anchor") if L.get("anchor") in sids else hero,
                               "placement": str(L.get("placement") or ""), "notes": str(L.get("notes") or ""),
                               "box": box, "rotate": rot})
        cv = lp.get("canvas") if isinstance(lp.get("canvas"), dict) else {}
        canvas = {"content_width_px": cv.get("content_width_px") if isinstance(cv.get("content_width_px"), int) else 1200,
                  "gutter_px": cv.get("gutter_px") if isinstance(cv.get("gutter_px"), int) else 24,
                  "canvas_use": str(cv.get("canvas_use") or "")}
        return {"layout_plan": {"canvas": canvas, "sections": secs, "layers": layers}}
    return None


def run_agent(ctx: Ctx, st: S.State, agent: str, schema: dict, build, default, force: bool, trace: list,
              extra_key=None) -> dict:
    ctx.progress({"kind": "start", "agent": agent})
    out = _run_agent(ctx, st, agent, schema, build, default, force, trace, extra_key)
    t = trace[-1] if trace and trace[-1].get("agent") == agent else {}
    ctx.progress({"kind": "done", "agent": agent, "source": t.get("source"), "model": t.get("model"), "ms": t.get("ms")})
    return out


def _run_agent(ctx: Ctx, st: S.State, agent: str, schema: dict, build, default, force: bool, trace: list,
               extra_key=None) -> dict:
    slc = S.slice_for(st, agent)
    dig = S.digest(st) if agent in ("a2", "a3", "a4") else None
    sys_text = prompt(agent) + (prompt("preamble") if dig is not None else "")
    k = cache.key(agent, sys_text, schema, S.compact(slc), S.compact(dig) if dig else "", extra_key or "")
    t = {"agent": agent, "slice_chars": len(S.compact(slc)), "digest_chars": len(S.compact(dig)) if dig else 0}
    if not force:
        rec = cache.get(agent, k)
        if rec:
            trace.append({**t, "source": "cache", "model": rec.get("model"), "usage": rec.get("usage"), "ms": 0})
            return rec["output"]
    if not ctx.enabled:
        trace.append({**t, "source": "default", "why": "agents off"})
        return default()
    errors, tried, model, meta, outs = [], [], None, {}, []

    def check(o) -> list[str]:
        try:
            jsonschema.validate(o, schema)
            return semantic(agent, o)
        except jsonschema.ValidationError as e:          # a schema miss gets the repair call too, not the default
            return [f"schema: {e.message[:200]} (at {'/'.join(str(p) for p in e.absolute_path) or 'top'})"]
    try:
        out, model, meta, tried = call(ctx, agent, build(None), MAX_OUT[agent])
        out = lenient(st, agent, out)
        outs.append(out)
        errors = check(out)
        if errors:                                       # one repair call: the same contract plus what failed
            # A2 (the user's call, R0): a model whose plan broke its schema hands the repair to the next model
            skip = {model} if agent in SALVAGE and any(e.startswith("schema:") for e in errors) else None
            out2, model2, meta2, tried2 = call(ctx, agent, build(errors), MAX_OUT[agent], skip=skip)
            tried += tried2
            out2 = lenient(st, agent, out2)
            outs.append(out2)
            e2 = check(out2)
            if not e2:
                out, model, meta = out2, model2, {**meta2, "repaired": True}
                errors = []
            else:
                errors += e2
    except (NoModel, ProviderError) as e:
        errors.append(f"{type(e).__name__}: {str(e)[:300]}")
        tried = tried or getattr(e, "tried", [])
    if errors and outs and agent in SALVAGE:
        sv = salvage(st, agent, outs)
        if sv is not None and not check(sv):
            n_s = len(sv["layout_plan"]["sections"])
            keys.notify(f"{agent.upper()}: the plan failed its checks; kept the {n_s} usable section(s) and "
                        f"{len(sv['layout_plan']['layers'])} layer(s), code fills the rest")
            trace.append({**t, "source": "salvaged", "why": errors[:3], "tried": tried, "model": model,
                          "key": meta.get("key"), "usage": meta.get("usage"), "ms": meta.get("ms")})
            return sv
    if errors and ctx.enabled and no_defaults():
        for n, wait in enumerate(RETRY_WAITS, 1):
            keys.notify(f"{agent.upper()}: no model could answer ({'; '.join(errors)[:140]}); waiting {wait:.0f}s, "
                        f"then asking the whole chain again ({n}/{len(RETRY_WAITS)}) - no canned default")
            ctx.progress({"kind": "wait", "agent": agent, "s": wait, "round": n})
            time.sleep(wait)
            try:
                out, model, meta, tried2 = call(ctx, agent, build(None), MAX_OUT[agent], fresh=True)
                tried += tried2
                out = lenient(st, agent, out)
                e3 = check(out)
                if e3 and agent in SALVAGE:
                    sv = salvage(st, agent, [out])
                    if sv is not None and not check(sv):
                        out, e3 = sv, []
                if not e3:
                    cache.put(agent, k, {"output": out, "model": model, "usage": meta.get("usage"),
                                         "at": time.strftime("%Y-%m-%d %H:%M:%S")})
                    trace.append({**t, "source": "model", "model": model, "key": meta.get("key"),
                                  "usage": meta.get("usage"), "ms": meta.get("ms"), "tried": tried,
                                  "retry_round": n})
                    return out
                errors = e3
            except (NoModel, ProviderError) as e:
                errors = [f"{type(e).__name__}: {str(e)[:300]}"]
                tried += getattr(e, "tried", [])
        trace.append({**t, "source": "unavailable", "why": errors[:3], "tried": tried})
        raise AgentUnavailable(agent, tried, "; ".join(errors)[:200])
    if errors:
        trace.append({**t, "source": "default", "why": errors[:3], "tried": tried, "model": model})
        return default()
    depth = None
    if agent == "a1" and ctx.enabled:
        out, model, meta, tried, depth = deepen_a1(ctx, st, schema, build, out, model, meta, tried)
    cache.put(agent, k, {"output": out, "model": model, "usage": meta.get("usage"), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    trace.append({**t, "source": "repaired" if meta.get("repaired") else "model", "model": model,
                  "key": meta.get("key"), "usage": meta.get("usage"), "est_in": meta.get("est_in"),
                  "ms": meta.get("ms"), "tried": tried, **({"depth": depth} if depth else {})})
    return out


A1_DEEPEN = ("expand", "fresh")   # the user's call (11-28): A1 has a floor. A thin document first goes back with what it
#                                   lacks (an expansion keeps every observation, the chain's current model first); if it
#                                   is still under A1_MIN, a vision model that hasn't tried writes a fresh one. The
#                                   deepest valid document goes on; `floor_met` records whether it reached A1_MIN.


def deepen_a1(ctx: Ctx, st: S.State, schema: dict, build, out, model, meta, tried):
    """A1's document under A1_MIN -> an expansion call, then (still thin) a fresh document from another vision model;
    the deepest valid document is kept. -> (out, model, meta, tried, depth record)."""
    m1 = a1_measure(out)
    why = a1_thin(m1)
    if not why:
        return out, model, meta, tried, {"first": m1, "floor_met": True}
    rec = {"first": {**m1, "model": model}, "thin": why, "attempts": []}
    best = {"score": m1["score"], "out": out, "model": model, "meta": meta}
    ms, seen = meta.get("ms") or 0, {model}
    for mode in A1_DEEPEN:
        short = a1_thin(a1_measure(best["out"]))
        if not short:
            break
        keys.notify(f"A1: {best['model']}'s design document is under the floor ({'; '.join(short)}); "
                    + ("sending it back to be expanded" if mode == "expand" else "asking another vision model for a fresh one"))
        ctx.progress({"kind": "retry", "agent": "a1", "model": best["model"], "why": f"thin: {mode}"})
        try:
            b = build(None, prev=best["out"], short=short) if mode == "expand" else build(None)
            o2, m2_model, meta2, t2 = call(ctx, "a1", b, MAX_OUT["a1"], skip=None if mode == "expand" else seen)
            tried = tried + t2
            seen.add(m2_model)
            ms += meta2.get("ms") or 0
            o2 = lenient(st, "a1", o2)
            jsonschema.validate(o2, schema)
            bad = semantic("a1", o2)
            m2 = a1_measure(o2)
            rec["attempts"].append({**m2, "mode": mode, "model": m2_model, "valid": not bad})
            if not bad and m2["score"] > best["score"]:
                best = {"score": m2["score"], "out": o2, "model": m2_model, "meta": meta2}
        except (NoModel, ProviderError, jsonschema.ValidationError) as e:
            rec["attempts"].append({"mode": mode, "error": f"{type(e).__name__}: {str(e)[:160]}"})
    if rec["attempts"]:
        rec["second"] = rec["attempts"][-1]            # the R-report's column (one retry used to be the whole story)
    mb = a1_measure(best["out"])
    rec["kept"] = {**mb, "model": best["model"]}
    rec["floor_met"] = not a1_thin(mb)
    if not rec["floor_met"]:
        keys.notify(f"A1: still under the floor after {len(rec['attempts'])} more call(s) ({'; '.join(a1_thin(mb))}); "
                    f"the deepest document ({best['model']}) goes on")
    return best["out"], best["model"], {**best["meta"], "ms": ms}, tried, rec


def _groq_msgs(st: S.State, agent: str, slc: dict, image: str | None, errors,
               image_header: str = "") -> tuple[list, int]:
    pre = prompt("preamble") + S.compact(S.digest(st))
    user_text = "INPUT:\n" + S.compact(slc)
    if errors:
        user_text += "\n\nYour previous answer failed these checks; fix them:\n- " + "\n- ".join(errors)
    content = user_text if not image else [{"type": "text", "text": user_text},
                                           {"type": "text", "text": image_header},
                                           {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image}"}}]
    msgs = [{"role": "system", "content": pre}, {"role": "system", "content": prompt(agent)},
            {"role": "user", "content": content}]
    est = budget.est_text(pre + prompt(agent) + user_text + image_header) + (budget.QWEN_IMAGE if image else 0)
    return msgs, est


TRIM_CAPS = (None, 260, 160, 100, 60, 45)    # 45 (11-28): deeper A1 documents + the design language


def chat_request(st: S.State, agent: str, schema: dict, errors, model: str) -> tuple:
    """The agent's chat request (Groq, or Mistral as the backup): the same shared preamble + digest prefix, its slice
    trimmed (longest descriptions first) until it fits the model's minute window (Mistral's is wide: no trim)."""
    kind = Ctx.pname(model)
    if kind == "gemini":                       # same words, Gemini's request shape: one system text + the user part
        msgs, _ = _groq_msgs(st, agent, S.slice_for(st, agent), None, errors)
        system = "\n\n".join(m["content"] for m in msgs if m["role"] == "system")
        return ("gemini", system, [{"text": msgs[-1]["content"]}], schema)
    slc = S.slice_for(st, agent)
    limit = budget.limits(model)["tpm"] * budget.MARGIN - GROQ_RESERVE.get(agent, int(MAX_OUT[agent] * 0.6))
    for cap in TRIM_CAPS:
        s = slc if cap is None else S.trim(slc, cap)
        msgs, sch, est = _with_schema(_groq_msgs(st, agent, s, None, errors), schema)
        if est <= limit:
            if cap:
                keys.notify(f"{agent.upper()}: descriptions trimmed to {cap} characters to fit {model}'s minute window")
            return (kind, msgs, sch, est)
    return (kind, msgs, sch, est)


groq_request = chat_request                       # the old name (lab / tests)


def problems(qa_res: dict | None) -> list[str]:
    return [f"{p} (at {w}px)" for w, r in (qa_res or {}).items() for p in r["problems"]]


MOTIF_COVERS = re.compile(r"motif (\S+) \(([^)]*)\) covers (?:text|image)")
BLOCKING_QA = ("overlaps text of", "horizontal overflow")


OVERFLOW_FIX = "html,body{overflow-x:clip}"     # decoration past the page edge: clipped, no scroll container (sticky works)
MIN_PAGE_TEXT = 60                               # visible characters below which a page has nothing to render


def classify(chk: dict, qa_res: dict | None, broken: str | None = None, strict: bool = False) -> dict:
    """-> {blocking, advisory, fix_motifs}: what discards a page, what is fed back, what code removes.
    A5's pages (strict=False, the user's call 2026-11-22): only a page that can't render is discarded (`broken`);
    every check (copy, hooks, h1 count, palette, overlap, overflow) is advice for the one repair round and ranks the
    candidates. The compile_spec fallback keeps the strict gate (strict=True) that drives its own measured repairs."""
    if strict:
        blocking, advisory = list(chk["errors"]), list(chk.get("advisories", []))
    else:
        blocking, advisory = ([broken] if broken else []), list(chk["errors"]) + list(chk.get("advisories", []))
    fix = set()
    for w, r in (qa_res or {}).items():
        for p in r["problems"]:
            m = MOTIF_COVERS.search(p)
            if strict and any(b in p for b in BLOCKING_QA):
                blocking.append(f"{p} (at {w}px)")
            elif m:
                fix.add(m.group(1))
            else:
                advisory.append(f"{p} (at {w}px)")
    return {"blocking": list(dict.fromkeys(blocking)), "advisory": list(dict.fromkeys(advisory)), "fix_motifs": fix}


# --------------------------------------------------------------------------- the run
def run(h: dict, *, enabled: bool = True, force_from: str | None = None, out_dir: Path | None = None,
        qa: bool = True, log=print, a5_repair: bool = True, progress=None, improve: bool = True) -> dict:
    """progress(event) (optional) hears every step: {kind: start | try | done, agent, model} for A1-A5,
    {kind: check} while A5's page is measured, {kind: start, agent: repair | fallback}, {kind: finish, source}."""
    from . import providers as P
    t0 = time.time()
    ctx = Ctx(enabled, log, progress)
    if enabled:
        keys.notify(f"models: {ctx.describe()}")
        first = {a: (ctx.chain(a) or ["code default"])[0].removeprefix(budget.OR_PREFIX) for a in ("a1", "a5", "a6")}
        log(f"A1 (sees the references) on {first['a1']} · A5 (composes) on {first['a5']} · A6 (improves what renders) "
            f"on {first['a6']}")
    st, trace, overrides = S.State(h), [], []
    forced = lambda a: force_from is not None and ORDER.index(a) >= ORDER.index(force_from)  # noqa: E731

    # A1 ---------------------------------------------------------------- visual director: the design document
    s1 = sc.a1()
    sent = S.present_images(h["images"])           # [(position, label, image)]: the numbering image_roles uses
    imgs = [(lbl, im) for _, lbl, im in sent]

    def build_a1(errors, prev=None, short=None):
        def b(model):
            text = "INPUT:\n" + S.compact(S.slice_for(st, "a1"))
            if errors:
                text += "\n\nYour previous answer failed these checks; fix them:\n- " + "\n- ".join(errors)
            if prev is not None:                      # the depth gate's expansion (deepen_a1)
                text += ("\n\nYOUR PREVIOUS DOCUMENT is below. It is too thin for the agents after you, who never see "
                         f"the images ({'; '.join(short or [])}). Return the COMPLETE document again in the same schema: "
                         "keep every observation and decision in it, and add what is missing. Write more in each "
                         "section's `what` (every component, the copy each carries by role, its colours, type level and "
                         "arrangement), fuller element `geometry`, and the type traits you saw. Look at the images again "
                         "for what you left out.\nPREVIOUS DOCUMENT:\n" + S.compact(prev))
            if model.startswith("gemini") or model.startswith("gemma"):
                parts = [{"text": text}]
                for pos, lbl, im in sent:             # each image announced by role: '[IMAGE 3 · palette: palette-image ...]'
                    parts += [{"text": sc.image_header(lbl, pos, im["cluster"], im["text"])},
                              {"image": im["local"], "res": A1_RES[lbl]}]
                return ("gemini", prompt("a1"), parts, s1)
            if ctx.pname(model) in ("openrouter", "modal", "deepseek"):   # text first, then each image after its header
                content = [{"type": "text", "text": text}]
                est = budget.est_text(prompt("a1") + text)
                for pos, lbl, im in sent:
                    head = sc.image_header(lbl, pos, im["cluster"], im["text"])
                    content += [{"type": "text", "text": head}, image_part_or(im["local"], OR_SIDE[A1_RES[lbl]])]
                    est += budget.est_text(head) + budget.OR_IMAGE[A1_RES[lbl]]
                msgs = [{"role": "system", "content": prompt("a1")}, {"role": "user", "content": content}]
                return (ctx.pname(model), msgs, s1, est)
            if ctx.pname(model) == "mistral":       # every image right after its role header, like Gemini's parts
                content = [{"type": "text", "text": text}]
                est = budget.est_text(prompt("a1") + text)
                for pos, lbl, im in sent:
                    head = sc.image_header(lbl, pos, im["cluster"], im["text"])
                    content += [{"type": "text", "text": head}, image_part(im["local"], A1_SIDE[A1_RES[lbl]])]
                    est += budget.est_text(head) + budget.MISTRAL_IMAGE[A1_RES[lbl]]
                msgs = [{"role": "system", "content": prompt("a1")}, {"role": "user", "content": content}]
                return ("mistral", msgs, s1, est)
            comp = P.composite_b64([(f"{pos} · {im['image']} · {lbl}", im["local"]) for pos, lbl, im in sent])
            legend = "\n".join(sc.image_header(lbl, pos, im["cluster"], im["text"]) for pos, lbl, im in sent)
            msgs = [{"role": "system", "content": prompt("a1")},
                    {"role": "user", "content": [{"type": "text", "text": text + "\n\nThe attached sheet holds every "
                                                  "reference image, each tile titled '<n> · <role-image> · <LABEL>':\n"
                                                  + legend},
                                                 {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{comp}"}}]}]
            return ("groq", msgs, s1, budget.est_text(prompt("a1") + text + legend) + budget.QWEN_IMAGE)
        return b
    a1 = run_agent(ctx, st, "a1", s1, build_a1, lambda: flow.default_doc(h), forced("a1"), trace,
                   extra_key=[im["ref_id"] for _, im in imgs])
    overrides += flow.after_a1(st, a1, h)

    # A2 ---------------------------------------------------------------- layout architect (Groq gpt-oss)
    s2 = sc.a2(*flow.a2_enums(st))
    a2 = run_agent(ctx, st, "a2", s2, lambda errs: (lambda model: groq_request(st, "a2", s2, errs, model)),
                   lambda: flow.default_plan(st), forced("a2"), trace)
    overrides += flow.after_a2(st, a2)

    # A3 ---------------------------------------------------------------- content editor (Groq gpt-oss)
    sids, _, colors = flow.a2_enums(st)
    s3 = sc.a3(sids, colors)
    a3 = run_agent(ctx, st, "a3", s3, lambda errs: (lambda model: groq_request(st, "a3", s3, errs, model)),
                   lambda: flow.default_copy(st, h), forced("a3"), trace)
    overrides += flow.after_a3(st, a3)

    # A4 ---------------------------------------------------------------- decor artist (Groq Qwen, text only)
    s4 = sc.a4(flow.a2_enums(st)[1])
    a4 = run_agent(ctx, st, "a4", s4, lambda errs: (lambda model: groq_request(st, "a4", s4, errs, model)),
                   lambda: flow.default_decor(st), forced("a4"), trace)
    overrides += flow.after_a4(st, a4)
    spec = flow.spec(st)
    st.put("code", "landing_spec", spec)

    # A5 ---------------------------------------------------------------- composer (Gemini) -> the gate
    import assets as A
    od = out_dir or (OUT / spatial_slug(h["meta"]["full_query"]))
    od.mkdir(parents=True, exist_ok=True)
    for old in list(od.glob("a5-*.html")) + list(od.glob("a6.html")):
        old.unlink()
    s_spec = S.compact(spec)
    k5 = cache.key("a5", prompt("a5"), s_spec)
    def build5(errs):
        user = s_spec + ("\n\nYour previous page was measured in a browser and checked; fix exactly these and keep "
                         "everything else (your composition, styling and decoration):\n- " + "\n- ".join(errs)
                         if errs else "")

        def b(model):
            if ctx.pname(model) == "gemini":
                return ("gemini", prompt("a5"), [{"text": user}], None)
            msgs = [{"role": "system", "content": prompt("a5")}, {"role": "user", "content": user}]
            return (ctx.pname(model), msgs, None, budget.est_text(prompt("a5") + user))
        return b
    cands: list[dict] = []

    def measure(page_html: str, sp: dict, shots: Path | None = None):
        write_site(od, page_html, sp, h, A)
        return QA.run(od / "index.html", spec=sp, shots_dir=shots) if qa else None

    def evaluate(raw: str, source: str, model: str | None, sp: dict | None = None) -> dict:
        """Safety sanitize (scripts, external URLs, handlers) + render + measure. Nothing else touches the page (the
        user's rule, R0 2026-11-26: "check if it renders, that's it"): no colour snapping, no decor moved or removed,
        no z-index clamp, no injected backdrop or items. Every check is reported; only a page that can't render is
        discarded."""
        n = len(cands) + 1
        sp = sp or spec
        chk = validate_page.check(raw, sp)
        body = chk["html"].split("<body", 1)[-1]
        q, broken = None, None
        if len(re.sub(r"<style.*?</style>|<[^>]+>|\s+", "", body, flags=re.S)) < MIN_PAGE_TEXT:
            broken = "the page has no content to render"
        else:
            try:
                q = measure(chk["html"], sp, od / "_shots" / str(n))
            except Exception as e:  # noqa: BLE001
                broken = f"the browser could not render the page ({type(e).__name__}: {str(e)[:120]})"
        c = classify(chk, q, broken)
        c["advisory"] += [f"decor {m} covers text or an image" for m in sorted(c["fix_motifs"])]
        c["style"] = style_check(q, sp)
        c["fix_motifs"] = set()
        name = "a6.html" if source == "improved" else f"a5-{n}.html"
        (od / name).write_text(chk["html"], encoding="utf-8")
        cand = {"n": n, "source": source, "model": model, "raw": raw, "chk": chk, "qa": q, **c, "fixes": chk["fixes"],
                "file": name}
        cands.append(cand)
        return cand

    alternates = font_alternates(st, spec)
    spec6 = with_fonts(spec, [a["family"] for a in alternates])

    def build6(base: dict):
        """The improver's request: the brief, what the browser measured, the page's screenshots (tiles, top to
        bottom), the composer's markup."""
        shots = od / "_shots" / str(base["n"])
        tiles = shot_tiles(shots)
        pics = [{"item_id": it["item_id"], "shows": it.get("description") or it.get("alt", ""), "aspect": it.get("aspect")}
                for sec in spec["sections"] for it in sec["items"] if it.get("kind") == "drawing"]
        imgs = [{"src": a["path"], "aspect": a.get("aspect"), "is": a.get("alt") or a.get("role")}
                for a in spec["assets"] if a.get("role") in ("image", "centerpiece")]
        brief = {"request": h["meta"]["full_query"], "brand": spec.get("title"),
                 "query_context": spec.get("query_context"), "aesthetic_direction": spec.get("aesthetic_direction"),
                 "palette": [f"var({c['var']}) {c['hex']} {c['name']}" for c in spec["colors"]],
                 "roles": spec.get("roles"),
                 "fonts": {lvl: {"stack": v.get("stack"), "category": font_info(v.get("family", ""))["category"],
                                 "weight": v.get("weight"), "size": v.get("size_css")}
                           for lvl, v in spec["typography"].items() if isinstance(v, dict)},
                 "font_alternates": alternates,
                 "font_findings": font_findings(base["qa"], spec),
                 "design_language": spec.get("design_language") or {},
                 "style_findings": style_check(base["qa"], spec)["findings"],
                 "pictures_to_draw": pics, "images_available": imgs,
                 "measured": problems(base["qa"])[:30] + base["blocking"][:3]}
        text = ("INPUT:\n" + S.compact(brief) + "\n\nThe screenshots follow, each after its header. Then THE PAGE.")
        page = "THE PAGE (the composer's markup):\n" + validate_page.strip_fences(base["raw"])

        def b(model):
            kind = ctx.pname(model)
            if kind == "gemini":
                parts = [{"text": text}]
                for label, path in tiles:
                    parts += [{"text": label}, {"image": str(path), "res": "high"}]
                parts.append({"text": page})
                return ("gemini", prompt("a6"), parts, None)
            content = [{"type": "text", "text": text}]
            est = budget.est_text(prompt("a6") + text + page)
            for label, path in tiles:
                content += [{"type": "text", "text": label},
                            image_part(path, A1_SIDE["high"]) if kind == "mistral" else image_part_or(path, 1536)]
                est += budget.est_text(label) + (budget.MISTRAL_IMAGE if kind == "mistral" else budget.OR_IMAGE)["high"]
            content.append({"type": "text", "text": page})
            return (kind, [{"role": "system", "content": prompt("a6")}, {"role": "user", "content": content}], None, est)
        return b
    rec = None if forced("a5") else cache.get("a5", k5)
    if rec:
        c1 = evaluate(rec["output"], "cache", rec.get("model"))
        trace.append({"agent": "a5", "source": "cache", "model": rec.get("model"), "usage": rec.get("usage"), "ms": 0,
                      "blocking": c1["blocking"][:4], "advisory": c1["advisory"][:6], "fixes": c1["fixes"]})
        if c1["blocking"]:
            cache.drop("a5", k5)
    ctx.progress({"kind": "start", "agent": "a5"})
    if not cands and ctx.enabled:
        tried = []
        try:
            raw, model, meta, tried = call(ctx, "a5", build5(None), MAX_OUT["a5"])
            ctx.progress({"kind": "check", "agent": "a5", "model": model, "ms": meta.get("ms")})
            c1 = evaluate(raw, "model", model)
            trace.append({"agent": "a5", "source": "model", "model": model, "key": meta.get("key"),
                          "usage": meta.get("usage"), "est_in": meta.get("est_in"), "ms": meta.get("ms"), "tried": tried,
                          "blocking": c1["blocking"][:4], "advisory": c1["advisory"][:6], "fixes": c1["fixes"],
                          "style": {k: c1["style"].get(k) for k in ("score", "deviations", "missing", "extra", "unowned")}})
        except (NoModel, ProviderError) as e:
            trace.append({"agent": "a5", "source": "fallback", "why": [str(e)[:300]],
                          "tried": tried or getattr(e, "tried", [])})
    base = next((c for c in cands if not c["blocking"]), None)
    last = cands[-1] if cands else None
    if not base and a5_repair and last and last["source"] == "model" and ctx.enabled and ctx.ring_left(last["model"]):
        # the page can't render: one repair round with what broke (a page that renders is never sent back)
        keys.notify(f"A5: {last['model']}'s page can't render ({'; '.join(last['blocking'])[:120]}); one repair")
        ctx.progress({"kind": "start", "agent": "repair", "model": last["model"]})
        outer = ctx.progress
        ctx.progress = lambda ev: outer({**ev, "agent": "repair"} if ev.get("agent") == "a5" else ev)  # P9: its own step
        try:
            raw2, model2, meta2, _ = call(ctx, "a5", build5(last["blocking"][:6]), MAX_OUT["a5"])
            c2 = evaluate(raw2, "repaired", model2)
            trace.append({"agent": "a5", "source": "repaired", "model": model2, "key": meta2.get("key"),
                          "usage": meta2.get("usage"), "ms": meta2.get("ms"), "why": last["blocking"][:6],
                          "blocking": c2["blocking"][:4], "advisory": c2["advisory"][:6], "fixes": c2["fixes"]})
            base = c2 if not c2["blocking"] else None
        except (NoModel, ProviderError) as e:
            trace.append({"agent": "a5", "source": "repair failed", "why": [str(e)[:200]]})
        finally:
            ctx.progress = outer
    if not base and ctx.enabled and no_defaults():
        for n, wait in enumerate(RETRY_WAITS, 1):         # no page that renders yet: ask the chain again, never canned
            keys.notify(f"A5: no page that renders yet; waiting {wait:.0f}s, then asking again ({n}/{len(RETRY_WAITS)})")
            ctx.progress({"kind": "wait", "agent": "a5", "s": wait, "round": n})
            time.sleep(wait)
            try:
                raw_r, model_r, meta_r, tried_r = call(ctx, "a5", build5(None), MAX_OUT["a5"], fresh=True)
                c_r = evaluate(raw_r, "model", model_r)
                trace.append({"agent": "a5", "source": "model", "model": model_r, "key": meta_r.get("key"),
                              "usage": meta_r.get("usage"), "ms": meta_r.get("ms"), "tried": tried_r,
                              "retry_round": n, "blocking": c_r["blocking"][:4], "advisory": c_r["advisory"][:6]})
                if not c_r["blocking"]:
                    base = c_r
                    break
            except (NoModel, ProviderError) as e:
                trace.append({"agent": "a5", "source": "unavailable", "why": [str(e)[:300]], "retry_round": n})
        if not base:
            tried_all = [x for t in trace if t.get("agent") == "a5" for x in (t.get("tried") or [])]
            raise AgentUnavailable("a5", tried_all, "; ".join(cands[-1]["blocking"])[:200] if cands else "")
    improved = None
    if base and ctx.enabled and improve:
        # A6, the improver (the user's P1 + P4 + P6): a vision model sees A5's page rendered and returns it improved
        ctx.progress({"kind": "start", "agent": "a6"})
        tried6 = []
        k6 = cache.key("a6", prompt("a6"), s_spec, base["raw"])
        rec6 = None if forced("a6") else cache.get("a6", k6)
        try:
            if rec6:
                raw6, model6, meta6 = rec6["output"], rec6.get("model"), {"ms": 0, "usage": rec6.get("usage")}
            else:
                try:
                    raw6, model6, meta6, tried6 = call(ctx, "a6", build6(base), MAX_OUT["a6"])
                except (NoModel, ProviderError) as e0:
                    # A/B run 2026-11-26: 5 of 6 improvers found every model busy at once (Gemini 503s) and gave
                    # up at once. One wait, then the whole chain again, cooldowns ignored; then A5's page ships.
                    if not no_defaults():
                        raise
                    wait = RETRY_WAITS[0]
                    tried6 = list(getattr(e0, "tried", []) or [])
                    keys.notify(f"A6: no improver could answer ({str(e0)[:120]}); waiting {wait:.0f}s, then asking "
                                f"the whole chain again (1/1)")
                    ctx.progress({"kind": "wait", "agent": "a6", "s": wait, "round": 1})
                    time.sleep(wait)
                    raw6, model6, meta6, t2 = call(ctx, "a6", build6(base), MAX_OUT["a6"], fresh=True)
                    tried6 += t2
            c6 = evaluate(raw6, "improved", model6, spec6)
            trace.append({"agent": "a6", "source": "cache" if rec6 else "model", "model": model6, "key": meta6.get("key"),
                          "usage": meta6.get("usage"), "est_in": meta6.get("est_in"), "ms": meta6.get("ms"),
                          "tried": tried6, "blocking": c6["blocking"][:4], "advisory": c6["advisory"][:6],
                          "improves": base["file"],
                          "fonts": {"findings": font_findings(base["qa"], spec), "before": font_roles(base["qa"]),
                                    "after": font_roles(c6["qa"])},
                          "style": {"before": {k: base["style"].get(k) for k in ("score", "deviations", "unowned")},
                                    "after": {k: c6["style"].get(k) for k in ("score", "deviations", "unowned")},
                                    "findings": base["style"].get("findings", [])[:8]}})
            kept, kept0 = copy_kept(c6["chk"]["html"], spec), copy_kept(base["chk"]["html"], spec)
            s5, s6 = base["style"].get("score"), c6["style"].get("score")
            strays = s5 is not None and s6 is not None and s6 > s5 + STYLE_SLACK
            if not c6["blocking"] and kept >= kept0 - 0.25 and strays:
                keys.notify(f"A6: the improved page strays from A1's design language (style score {s6}, A5's {s5}); "
                            f"A5's ships")
                trace[-1]["rejected"] = f"strays from A1's design language: style score {s6}, A5's page {s5}"
            elif not c6["blocking"] and kept >= kept0 - 0.25:
                improved = c6
                if not rec6:
                    cache.put("a6", k6, {"output": raw6, "model": model6, "usage": meta6.get("usage")})
            elif not c6["blocking"]:            # it renders, but most of the page's words are gone: not this page
                keys.notify(f"A6: the improved page kept {kept:.0%} of the copy (A5's: {kept0:.0%}); A5's ships")
                trace[-1]["rejected"] = f"kept {kept:.0%} of the copy, A5's page {kept0:.0%}"
            else:
                keys.notify(f"A6: the improved page can't render ({'; '.join(c6['blocking'])[:120]}); A5's ships")
            ctx.progress({"kind": "done", "agent": "a6", "source": "model", "model": model6, "ms": meta6.get("ms")})
        except (NoModel, ProviderError) as e:
            trace.append({"agent": "a6", "source": "failed", "why": [str(e)[:300]],
                          "tried": tried6 or getattr(e, "tried", [])})
            keys.notify(f"A6: no improver answered ({str(e)[:120]}); A5's page ships")
            ctx.progress({"kind": "done", "agent": "a6", "source": "failed"})
    best = improved or base
    if best:
        page, source, qa_res = best["chk"], best["source"], best["qa"]
        write_site(od, page["html"], spec, h, A)
        if base and base["source"] in ("model", "repaired"):
            cache.put("a5", k5, {"output": base["raw"], "model": base["model"]})
    else:                                                # the deterministic compile_spec page, same design document
        why = "agents off" if not ctx.enabled else (cands[-1]["blocking"][:4] if cands else "no model page")
        ctx.progress({"kind": "start", "agent": "fallback"})
        if cands:
            cache.drop("a5", k5)
        spec, flog = flow.fallback(st, h)
        overrides += flog
        page = validate_page.check(compile_spec.render(spec), spec)
        qa_res = measure(page["html"], spec) if not page["errors"] else None
        for _round in range(2):                          # repair what the browser measured, recheck
            c = classify(page, qa_res, strict=True)
            if not (c["blocking"] or c["fix_motifs"]):
                break
            spec2, fix = qa_repair(spec, problems(qa_res))
            if not fix:
                break
            overrides += fix
            spec = spec2
            page = validate_page.check(compile_spec.render(spec), spec)
            qa_res = measure(page["html"], spec) if not page["errors"] else None
        c = classify(page, qa_res, strict=True)
        source = "compile_spec"
        if c["blocking"] or c["fix_motifs"]:            # last resort: known-clean by construction
            spec, slog = flow.safe(st, h)
            overrides += slog
            page = validate_page.check(compile_spec.render(spec), spec)
            qa_res = measure(page["html"], spec)
            source = "safe_spec"
        if not qa:
            write_site(od, page["html"], spec, h, A)
        trace.append({"agent": "a5", "source": source, "why": why})
    result = {"out": str(od), "url_path": "index.html", "page_source": source, "trace": trace,
              "overrides": overrides + [{"token": "page", "from": None, "to": None, "why": e} for e in page["errors"]],
              "warnings": page["warnings"], "qa": qa_res, "spec": spec,
              "candidates": [{k: c[k] for k in ("n", "source", "model", "blocking", "advisory", "fixes", "file")}
                             for c in cands],
              "raw": {k: st.get(k) for k in ("design_doc", "layout_plan", "copy", "decor")},
              "a1_depth": a1_depth(st.get("design_doc")),
              "ledger": ctx.quota(sorted({m for t in trace for m in [t.get("model")] if m})),
              "ms": int((time.time() - t0) * 1000)}
    (od / "result.json").write_text(json.dumps({k: v for k, v in result.items() if k != "spec"}, indent=1, default=str),
                                    encoding="utf-8")
    ctx.progress({"kind": "finish", "source": source})
    return result


COMPONENT_OF = {"cta": "button", "card": "card", "label": "tag", "image": "image_frame", "drawing": "image_frame",
                "centerpiece": "image_frame"}
STYLE_SLACK = 2            # A6's page may stray this much more from A1's design language than A5's before A5's ships


def style_check(qa_res: dict | None, spec: dict) -> dict:
    """The built page against A1's design language at 1440 px (the user's call, 11-28): components whose corners or
    shadow contradict A1's component styles, A1 decor elements missing from the page, motifs A1 never named, and
    decorative shapes no A1 element owns. -> {findings, deviations, missing, extra, unowned, score}; score None when
    the page wasn't measured."""
    r = ((qa_res or {}).get(1440) or {}).get("style")
    if not r:
        return {"findings": [], "score": None}
    want = {c["component"]: c for c in (spec.get("design_language") or {}).get("component_styles", [])}
    kind = {x["item_id"]: x["kind"] for x in spec.get("items", [])}
    groups: dict[tuple, list] = {}
    for it in r.get("items", []):
        comp = COMPONENT_OF.get(kind.get(it["id"]))
        w = want.get(comp)
        if not w:
            continue
        rad, m = w["radius_px"], it["radius"]
        pill = rad >= 100
        # corners only show on a painted box (a fill, image or border): plain text has no shape to judge
        ok = not it.get("painted", True) or (m >= 0.45 * min(it["w"], it["h"]) if pill
                                              else abs(m - rad) <= max(3.0, 0.35 * rad))
        if not ok:
            groups.setdefault((comp, f"{m:g}px corners", "pill / fully round" if pill else f"{rad:g}px corners"),
                              []).append(it["id"])
        if w["shadow"] == "none" and it["shadow"]:
            groups.setdefault((comp, "a box shadow", "no shadow"), []).append(it["id"])
    findings = [f"{comp} {', '.join(ids[:3])}{' +' + str(len(ids) - 3) if len(ids) > 3 else ''}: built with {got}; "
                f"A1's design language says {need} ({want[comp]['shape'][:90]})" for (comp, got, need), ids in groups.items()]
    a1_ids = [d["element_id"] for d in spec.get("decor", []) if d.get("asset")]
    on = set(r.get("motifs", []))
    missing = [e for e in a1_ids if e not in on]
    items = set(kind)                       # a picture A1 asked for, tagged with the motif hook, is not decoration
    extra = sorted(m for m in on if m not in a1_ids and m not in items)
    unowned = r.get("unowned", [])
    findings += [f"A1's decor element '{e}' is not on the page" for e in missing[:4]]
    findings += [f"motif '{m}' is not one of A1's elements: decoration comes only from A1's list" for m in extra[:4]]
    if unowned:
        eg = "; ".join(f"{u['kind']} {u.get('on', '')}" + (f" {u['w']}x{u['h']}" if u.get("w") else "") for u in unowned[:5])
        findings.append(f"{len(unowned)} decorative shape(s) no A1 element owns ({eg}): remove them, or build that "
                        f"decoration as one of A1's elements")
    dev = sum(len(v) for v in groups.values())
    return {"findings": findings[:14], "deviations": dev, "missing": missing, "extra": extra, "unowned": len(unowned),
            "score": dev + len(missing) + len(extra) + len(unowned)}


A6_ALTERNATES = 4          # loaded faces A6 may swap in when a level's face reads badly (the user's call, 11-28)
READABLE = ("Sans Serif", "Serif")


def font_alternates(st: S.State, spec: dict, n: int = A6_ALTERNATES) -> list[dict]:
    """Faces from A1's pool that the page doesn't use yet, readable categories first -> [{family, stack, ...}]."""
    have = {f.lower() for f in spec.get("fonts", [])}
    pool = [(f, i) for f, i in (st.get("font_pool") or {}).items() if f.lower() not in have]
    pool.sort(key=lambda x: x[1].get("category") not in READABLE)
    return [{"family": f, "stack": S.font_stack(f), "category": i.get("category"), "weights": i.get("weights"),
             "tags": i.get("tags")} for f, i in pool[:n]]


def with_fonts(spec: dict, fams: list[str]) -> dict:
    """The spec with more faces loaded (Google Fonts links) and allowed by the page checks."""
    new = [f for f in fams if f.lower() not in {x.lower() for x in spec.get("fonts", [])}]
    return {**spec, "fonts": list(spec.get("fonts", [])) + new,
            "fonts_css": list(spec.get("fonts_css", [])) + [S.g.google_css(f, False) for f in new]}


def font_roles(qa_res: dict | None) -> dict:
    """At 1440 px: which face sets how many text runs (to see what A6 moved)."""
    r = ((qa_res or {}).get(1440) or {}).get("readability") or {}
    return {f: d["runs"] for f, d in (r.get("fonts") or {}).items()}


def font_findings(qa_res: dict | None, spec: dict) -> list[str]:
    """What the browser measured about the faces: a display / handwriting face set at body size, text set very
    small, a face that never loaded (the page shows a fallback)."""
    out = []
    want = spec.get("fonts") or []
    for w in sorted(qa_res or {}, reverse=True):
        rd = (qa_res[w] or {}).get("readability") or {}
        if rd.get("loaded") is not None and w == max(qa_res):
            lo = {x.lower() for x in rd["loaded"]}
            out += [f"face '{f}' did not load: the browser draws a fallback face where it is used"
                    for f in want if f.lower() not in lo]
        for fam, d in (rd.get("fonts") or {}).items():
            cat = font_info(fam)["category"] if fam else ""
            if cat in ("Display", "Handwriting") and (d["small"] or d["long_small"]):
                out.append(f"'{fam}' ({cat.lower()} face) sets {d['small']} text run(s) under 16 px and "
                           f"{d['long_small']} long run(s) under 20 px at {w}px, smallest {d['min_px']:g} px "
                           f"(\"{d['sample']}\", in {', '.join(d['tags'])})")
            elif d["min_px"] < 12:
                out.append(f"'{fam}' is set as small as {d['min_px']:g} px at {w}px (\"{d['sample']}\")")
    return list(dict.fromkeys(out))[:12]


def copy_kept(html: str, spec: dict) -> float:
    """Share of the spec's copy strings that appear on the page (the same folding as validate_page's check)."""
    want = [x for x in spec.get("copy", []) if x]
    if not want:
        return 1.0
    body = html.split("<body", 1)[-1]
    text = validate_page._norm(re.sub(r"<style.*?</style>|<[^>]+>", " ", body, flags=re.S) + " " +
                               " ".join(re.findall(r'(?:placeholder|value)="([^"]*)"', body)))
    return sum(1 for x in want if validate_page._norm(x) in text) / len(want)


def shot_tiles(shots: Path) -> list[tuple[str, Path]]:
    """The measured page's screenshots cut into screen-sized tiles (a provider shrinks an image's long side to ~1536
    px, which would make a whole page unreadable) -> [(header, path)], desktop top to bottom, then the phone."""
    from PIL import Image
    out = []
    for name, kind, label in (("1440_full.jpg", "desktop", "DESKTOP 1440 px"), ("390_full.jpg", "phone", "PHONE 390 px")):
        f = shots / name
        if not f.exists():
            continue
        th, most = SHOT_TILE[kind]
        with Image.open(f) as im:
            im = im.convert("RGB")
            # tiles are cut on the shot's own scale: the desktop shot is 960 px wide for a 1440 px page
            scale = 1440 / im.width if kind == "desktop" else 390 / im.width
            step = int(th / scale) if kind == "desktop" else th
            n = min(most, max(1, -(-im.height // step)))
            for i in range(n):
                y0 = i * step
                if y0 >= im.height:
                    break
                tile = im.crop((0, y0, im.width, min(im.height, y0 + step)))
                p = shots / f"{kind}_{i + 1}.jpg"
                tile.save(p, "JPEG", quality=84)
                more = " (the page continues below)" if i == n - 1 and y0 + step < im.height else ""
                out.append((f"[{label} · part {i + 1} of {n} · page y {int(y0 * scale)}-"
                            f"{int(min(im.height, y0 + step) * scale)} px{more}]", p))
    return out


def a1_depth(doc: dict | None) -> dict:
    """How much A1 actually observed: colours and elements traced to a reference image, elements with geometry."""
    if not isinstance(doc, dict):
        return {}
    cols = [c for g in (doc.get("color_palette_distribution") or {}).values() for c in g or []]
    els = ((doc.get("background_layer") or {}).get("elements") or []) + (doc.get("midground_decor") or []) + \
        (doc.get("foreground_overlays") or [])
    seen = lambda x: (x.get("source") or "inferred") != "inferred"  # noqa: E731
    return {"colours": len(cols), "colours_traced": sum(1 for c in cols if seen(c)), "elements": len(els),
            "elements_traced": sum(1 for e in els if seen(e)),
            "elements_with_geometry": sum(1 for e in els if len((e.get("geometry") or "").strip()) >= 20),
            "sections": len(doc.get("content_sections") or [])}


DEAD_CARD = re.compile(r"dead space: (\S+) is")


def qa_repair(spec: dict, problems_: list[str]) -> tuple[dict, list]:
    """The fallback page: what the browser measured beats the plan. Drop a motif that covers text or an image; let
    cards size to their own content when a row's equal heights leave a card mostly empty. -> (new spec, overrides)."""
    spec, log = json.loads(json.dumps(spec)), []
    drop = {m.group(1) for p in problems_ for m in [MOTIF_COVERS.search(p)] if m}
    if drop:
        spec["motifs"] = [m for m in spec["motifs"] if m["motif_id"] not in drop]
        spec["motif_ids"] = [i for i in spec["motif_ids"] if i not in drop]
        log += [{"token": i, "from": "motif", "to": None, "why": "browser: it covered text or an image"} for i in sorted(drop)]
    cards = {x["item_id"] for x in spec["items"] if x["kind"] == "card"}
    if any(m and m.group(1) in cards for p in problems_ for m in [DEAD_CARD.search(p)]) \
            and spec["layout"].get("cards_align") != "start":
        spec["layout"]["cards_align"] = "start"
        log.append({"token": "cards.align", "from": "stretch", "to": "start",
                    "why": "browser: equal row heights left a card mostly empty"})
    return spec, log


def _with_schema(msgs_est: tuple[list, int], schema: dict) -> tuple[list, dict, int]:
    msgs, est = msgs_est
    return msgs, schema, est + budget.est_text(json.dumps(sc.provider_schema(schema), separators=(",", ":")))


def spatial_slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (s or "site").lower()).strip("-")[:48] or "site"


def write_site(od: Path, html: str, spec: dict, h: dict, A) -> None:
    (od / "assets").mkdir(parents=True, exist_ok=True)
    (od / "index.html").write_text(html, encoding="utf-8")
    (od / "spec.json").write_text(json.dumps(spec, indent=1), encoding="utf-8")
    local = {a["path"]: a["local"] for a in h["assets"]}
    for a in spec["assets"]:
        f = od / a["path"]
        src = local.get(a.get("from") or a["path"])
        if f.exists() or not src:
            continue
        data = A.web_image(Path(src))
        if a.get("blur"):                                # an off-subject backdrop: only its colour and light carry
            import io
            from PIL import Image, ImageFilter
            im = Image.open(io.BytesIO(data)).convert("RGB")
            im = im.resize((max(1, im.width // 2), max(1, im.height // 2))).filter(ImageFilter.GaussianBlur(a["blur"] / 2))
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=78)
            data = buf.getvalue()
        f.write_bytes(data)
