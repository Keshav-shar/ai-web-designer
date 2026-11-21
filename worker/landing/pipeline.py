"""pipeline.py - run the five agents over a handoff and write the landing page.

    run(handoff, enabled=True|False, force_from=None, out_dir=..., qa=True) -> result

The agents write one design document together (state.py): A1 (Mistral vision, sees the five reference images, each
after its role header) describes the whole visual system in words, A2 plans the layout, A3 writes the copy, A4 draws
the decorations (A2-A4 on Groq, Mistral as their backup), and A5 (Mistral, text only) composes the page from the
merged document with real design freedom. Gemini is only the last fallback for A1 / A5.

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

from . import budget, cache, compile_spec, defaults, flow, keys, qa as QA, schemas as sc, state as S, validate_page
from .providers import Gemini, Groq, Mistral, ProviderError, image_part

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
PREFS = {"mistral:vision": ["mistral-medium-latest", "ministral-14b-latest"],
         "mistral:compose": ["mistral-medium-latest", "codestral-latest", "ministral-14b-latest"],
         "mistral:text": ["mistral-medium-latest", "ministral-8b-latest", "ministral-14b-latest"],
         "gemini": ["gemini-4-hydrogen", "gemini-3.8-flash"], "groq:big": ["openai/gpt-oss-120b"],
         "groq:vision": ["qwen/qwen3.8-27b"]}
CHAINS = {"a1": ["mistral:vision", "gemini"], "a2": ["groq:big", "mistral:text"], "a3": ["groq:big", "mistral:text"],
          "a4": ["groq:vision", "groq:big", "mistral:text"], "a5": ["mistral:compose", "gemini"]}
# A4 is text-only (A1 describes the images); Qwen keeps its own minute window apart from A2/A3's gpt-oss.
# If every model of a chain is out, the agent falls back to code (the default document / compile_spec).
MISTRAL_PREFIXES = ("mistral", "ministral", "magistral", "pixtral", "devstral", "codestral")
A1_SIDE = {"high": 1540, "medium": 1024, "low": 1024}   # Mistral: <=1540 px, ~(W*H)/784 tokens per image
MAX_OUT = {"a1": 9000, "a2": 3000, "a3": 3000, "a4": 4000, "a5": 20000}
TEMP = {"a1": 0.5, "a2": 0.4, "a3": 0.6, "a4": 0.7, "a5": 0.7}
THINK = {"a1": "medium", "a5": "medium"}            # Gemini thinking level per agent (others: low)
A1_RES = {"LAYOUT_REF": "high", "TYPOGRAPHY_REF": "high", "ELEMENTS_REF": "medium", "BACKGROUND_REF": "medium",
          "PALETTE_REF": "low"}
WAIT_MAX = 25.0                         # longer waits for a minute window -> try the next model instead
WAIT_MAX_MISTRAL = 65.0                 # Mistral's free tier is 2 req/min: waiting out the minute is normal there
TIMEOUT = {"a1": 240.0, "a2": 60.0, "a3": 60.0, "a4": 60.0, "a5": 300.0}
STICKY_S = 1800.0                       # after a switch to the alternate, stay on it this long before retrying the primary
ORDER = ["a1", "a2", "a3", "a4", "a5"]


def prompt(name: str) -> str:
    return (PROMPTS / f"{name}.md").read_text(encoding="utf-8")


class NoModel(RuntimeError):
    def __init__(self, msg: str, tried: list | None = None):
        super().__init__(msg)
        self.tried = tried or []


class Ctx:
    def __init__(self, enabled: bool, log=print):
        self.enabled, self.log = enabled, log
        self.buckets, self.ledger = budget.Buckets(), budget.Ledger()
        self.gemini, self.groq, self.mistral = Gemini(), Groq(self.buckets), Mistral(self.buckets)
        self.rings = {p: keys.Ring(p if enabled else "") for p in ("mistral", "groq", "gemini")}
        self.resolved: dict[str, list[str]] = {}

    @staticmethod
    def pname(model: str) -> str:
        if model.startswith(("gemini", "gemma")):
            return "gemini"
        return "mistral" if model.startswith(MISTRAL_PREFIXES) else "groq"

    def resolve(self, alias: str) -> list[str]:
        """Alias -> its preferred models that this provider lists (checked with the first key that works)."""
        if alias not in self.resolved:
            name = alias.split(":", 1)[0]
            ring, prov = self.rings[name], {"gemini": self.gemini, "groq": self.groq, "mistral": self.mistral}[name]
            picks: list[str] = []
            for i in range(len(ring)):
                if i in ring.disabled:
                    continue
                try:
                    live = set(prov.models(ring.keys[i]))
                    picks = [m for m in PREFS[alias] if m in live]
                    if alias == "mistral:vision":
                        picks = [m for m in picks if prov.vision(m)]
                    break
                except ProviderError as e:
                    if e.kind == "auth":
                        ring.disable(i, str(e))
                        keys.notify(f"{ring.label(i)} was rejected ({str(e)[:80]}); skipping it this session")
                        continue
                    picks = list(PREFS[alias])             # can't list: try the preferences, let errors decide
                    break
            self.resolved[alias] = picks
        return self.resolved[alias]

    def chain(self, agent: str) -> list[str]:
        pinned = os.getenv(f"AGENT{agent[1]}_MODEL", "").strip()
        if pinned:
            return [m.strip() for m in pinned.split(",") if m.strip()]
        base = list(dict.fromkeys(m for a in CHAINS[agent] for m in self.resolve(a)))
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


def call(ctx: Ctx, agent: str, build, max_out: int) -> tuple[dict | str, str, dict, list]:
    """build(model) -> ("gemini", system, parts, schema) | ("groq" | "mistral", messages, schema, est_tokens).
    For each model in the agent's chain (the model that last answered for this chain goes first), each usable
    key in order: a daily limit marks that key out for the model (ledger), a per-minute limit cools the key and moves
    to the next one, a rejected key is skipped for the session. If every attempt failed only because of minute
    windows, wait once for the first window to reopen and go round again. Every switch prints one line on the
    terminal (keys.notify). -> (parsed output or text, model, reply meta incl. key label, tried[])."""
    tried = []
    chain = ctx.chain(agent)
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
            req = build(model)
            next_model = False
            for n, i in enumerate(order):
                key, kid, label = ring.keys[i], ring.ids[i], ring.label(i)
                later = order[n + 1:]
                nxt = ring.label(later[0]) if later else None
                cool = ring.cooling_for(i, model)        # keys come sorted by cooldown: if this one cools, all do
                if cool > WAIT_MAX:
                    tried.append({"model": model, "key": label, "skip": f"per-minute limit, cooling {cool:.0f}s"})
                    break
                if cool:
                    keys.notify(f"{label} is cooling down on {model}: waiting {cool:.0f}s")
                    time.sleep(cool)
                out_cap, t_key = max_out, time.time()
                strict = (model, agent) not in _NONSTRICT
                for attempt in range(3):
                    try:
                        if req[0] == "gemini":
                            _, system, parts, schema = req
                            est = budget.est_text(system + "".join(p.get("text", "") for p in parts)) + sum(
                                budget.GEMINI_IMAGE.get(p.get("res", "high"), 1120) for p in parts if "image" in p) + (
                                budget.est_text(json.dumps(schema, separators=(",", ":"))) if schema else 0)
                            reply = ctx.gemini.generate(model, system, parts, key=key, schema=schema, max_out=out_cap,
                                                        temperature=TEMP[agent], timeout=TIMEOUT[agent],
                                                        thinking=THINK.get(agent, "low"))
                        else:
                            kind, messages, schema, est = req
                            prov = ctx.mistral if kind == "mistral" else ctx.groq
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
                                                  timeout=TIMEOUT[agent])
                        u = reply.usage
                        ctx.ledger.record(model, u.get("in", 0) + u.get("out", 0) + u.get("thinking", 0), kid)
                        ctx.buckets.note(model, max(0, u.get("in", 0) - u.get("cached", 0)) + u.get("out", 0)
                                         + u.get("thinking", 0), kid)
                        data = reply.json() if (req[0] == "gemini" and req[3] is not None) or \
                            (req[0] != "gemini" and req[2] is not None) else reply.text
                        if model != (_PREFERRED.get(stick) or ("",))[0]:
                            _PREFERRED[stick] = (model, time.monotonic())
                        return data, model, {"ms": reply.ms, "usage": u, "headers": reply.headers, "key": label,
                                             "est_in": est, "strict": strict}, tried
                    except ProviderError as e:
                        if e.kind == "truncated" and attempt == 0:
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
                                        + " (skipped for this key for 6 h)")
                            tried.append({"model": model, "key": label, "skip": "not on this key's tier"})
                            minute_only = False
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
                        if e.kind == "timeout" and attempt == 0:   # slow is not broken: once more, same model
                            keys.notify(f"{agent.upper()}: {model} took over {TIMEOUT[agent]:.0f}s; retrying it once")
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


def run_agent(ctx: Ctx, st: S.State, agent: str, schema: dict, build, default, force: bool, trace: list,
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
    errors, tried, model, meta = [], [], None, {}
    try:
        out, model, meta, tried = call(ctx, agent, build(None), MAX_OUT[agent])
        jsonschema.validate(out, schema)
        errors = semantic(agent, out)
        if errors:                                       # one repair call: the same contract plus what failed
            out2, model, meta2, tried2 = call(ctx, agent, build(errors), MAX_OUT[agent])
            tried += tried2
            jsonschema.validate(out2, schema)
            if not semantic(agent, out2):
                out, meta = out2, {**meta2, "repaired": True}
                errors = []
    except (NoModel, jsonschema.ValidationError, ProviderError) as e:
        errors.append(f"{type(e).__name__}: {str(e)[:300]}")
        tried = tried or getattr(e, "tried", [])
    if errors:
        trace.append({**t, "source": "default", "why": errors[:3], "tried": tried, "model": model})
        return default()
    cache.put(agent, k, {"output": out, "model": model, "usage": meta.get("usage"), "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    trace.append({**t, "source": "repaired" if meta.get("repaired") else "model", "model": model,
                  "key": meta.get("key"), "usage": meta.get("usage"), "est_in": meta.get("est_in"),
                  "ms": meta.get("ms"), "tried": tried})
    return out


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


TRIM_CAPS = (None, 260, 160, 100, 60)


def chat_request(st: S.State, agent: str, schema: dict, errors, model: str) -> tuple:
    """The agent's chat request (Groq, or Mistral as the backup): the same shared preamble + digest prefix, its slice
    trimmed (longest descriptions first) until it fits the model's minute window (Mistral's is wide: no trim)."""
    kind = Ctx.pname(model)
    slc = S.slice_for(st, agent)
    limit = budget.limits(model)["tpm"] * budget.MARGIN - int(MAX_OUT[agent] * 0.6)
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


def classify(chk: dict, qa_res: dict | None) -> dict:
    """-> {blocking, advisory, fix_motifs}: what discards a page, what is fed back, what code removes."""
    blocking, advisory, fix = list(chk["errors"]), list(chk.get("advisories", [])), set()
    for w, r in (qa_res or {}).items():
        for p in r["problems"]:
            m = MOTIF_COVERS.search(p)
            if any(b in p for b in BLOCKING_QA):
                blocking.append(f"{p} (at {w}px)")
            elif m:
                fix.add(m.group(1))
            else:
                advisory.append(f"{p} (at {w}px)")
    return {"blocking": list(dict.fromkeys(blocking)), "advisory": list(dict.fromkeys(advisory)), "fix_motifs": fix}


# --------------------------------------------------------------------------- the run
def run(h: dict, *, enabled: bool = True, force_from: str | None = None, out_dir: Path | None = None,
        qa: bool = True, log=print, a5_repair: bool = True) -> dict:
    from . import providers as P
    t0 = time.time()
    ctx = Ctx(enabled, log)
    if enabled:
        keys.notify(f"models: {ctx.describe()}")
    st, trace, overrides = S.State(h), [], []
    forced = lambda a: force_from is not None and ORDER.index(a) >= ORDER.index(force_from)  # noqa: E731

    # A1 ---------------------------------------------------------------- visual director: the design document
    s1 = sc.a1()
    sent = S.present_images(h["images"])           # [(position, label, image)]: the numbering image_roles uses
    imgs = [(lbl, im) for _, lbl, im in sent]

    def build_a1(errors):
        def b(model):
            text = "INPUT:\n" + S.compact(S.slice_for(st, "a1"))
            if errors:
                text += "\n\nYour previous answer failed these checks; fix them:\n- " + "\n- ".join(errors)
            if model.startswith("gemini") or model.startswith("gemma"):
                parts = [{"text": text}]
                for pos, lbl, im in sent:             # each image announced by role: '[IMAGE 3 · palette: palette-image ...]'
                    parts += [{"text": sc.image_header(lbl, pos, im["cluster"], im["text"])},
                              {"image": im["local"], "res": A1_RES[lbl]}]
                return ("gemini", prompt("a1"), parts, s1)
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
    for old in od.glob("a5-*.html"):
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

    def measure(page_html: str, sp: dict):
        write_site(od, page_html, sp, h, A)
        return QA.run(od / "index.html", spec=sp) if qa else None

    def evaluate(raw: str, source: str, model: str | None) -> dict:
        """Sanitize + check + measure an A5 page; code removes decor that covers content and adds a missing backdrop."""
        chk = validate_page.check(raw, spec, inject_backdrop=True, fix_colors_=True)
        q = measure(chk["html"], spec) if not chk["errors"] else None
        c = classify(chk, q)
        if c["fix_motifs"]:
            chk = validate_page.check(raw, spec, drop_motifs=c["fix_motifs"], inject_backdrop=True, fix_colors_=True)
            q = measure(chk["html"], spec) if not chk["errors"] else None
            c = classify(chk, q)
        n = len(cands) + 1
        (od / f"a5-{n}.html").write_text(chk["html"], encoding="utf-8")
        cand = {"n": n, "source": source, "model": model, "raw": raw, "chk": chk, "qa": q, **c, "fixes": chk["fixes"],
                "file": f"a5-{n}.html"}
        cands.append(cand)
        return cand
    rec = None if forced("a5") else cache.get("a5", k5)
    if rec:
        c1 = evaluate(rec["output"], "cache", rec.get("model"))
        trace.append({"agent": "a5", "source": "cache", "model": rec.get("model"), "usage": rec.get("usage"), "ms": 0,
                      "blocking": c1["blocking"][:4], "advisory": c1["advisory"][:6], "fixes": c1["fixes"]})
        if c1["blocking"]:
            cache.drop("a5", k5)
    if not cands and ctx.enabled:
        tried = []
        try:
            raw, model, meta, tried = call(ctx, "a5", build5(None), MAX_OUT["a5"])
            c1 = evaluate(raw, "model", model)
            trace.append({"agent": "a5", "source": "model", "model": model, "key": meta.get("key"),
                          "usage": meta.get("usage"), "est_in": meta.get("est_in"), "ms": meta.get("ms"), "tried": tried,
                          "blocking": c1["blocking"][:4], "advisory": c1["advisory"][:6], "fixes": c1["fixes"]})
        except (NoModel, ProviderError) as e:
            trace.append({"agent": "a5", "source": "fallback", "why": [str(e)[:300]],
                          "tried": tried or getattr(e, "tried", [])})
    last = cands[-1] if cands else None
    if a5_repair and last and last["source"] == "model" and (last["blocking"] or last["advisory"]) and ctx.enabled \
            and ctx.ring_left(last["model"]):              # once per fresh page; a cached page already had its turn
        notes = last["blocking"] + last["advisory"]
        keys.notify(f"A5: {len(last['blocking'])} blocking / {len(last['advisory'])} advisory finding(s) on "
                    f"{last['model']}'s page; sending them back once")
        try:
            raw2, model2, meta2, _ = call(ctx, "a5", build5(notes[:10]), MAX_OUT["a5"])
            c2 = evaluate(raw2, "repaired", model2)
            trace.append({"agent": "a5", "source": "repaired", "model": model2, "key": meta2.get("key"),
                          "usage": meta2.get("usage"), "ms": meta2.get("ms"), "why": notes[:6],
                          "blocking": c2["blocking"][:4], "advisory": c2["advisory"][:6], "fixes": c2["fixes"]})
        except (NoModel, ProviderError) as e:
            trace.append({"agent": "a5", "source": "repair failed", "why": [str(e)[:200]]})
    ok = [c for c in cands if not c["blocking"]]
    best = min(ok, key=lambda c: (len(c["advisory"]), -c["n"])) if ok else None
    if best:
        page, source, qa_res = best["chk"], best["source"], best["qa"]
        write_site(od, page["html"], spec, h, A)
        if best["source"] in ("model", "repaired"):
            cache.put("a5", k5, {"output": best["raw"], "model": best["model"]})
        overrides += [{"token": "a5", "from": None, "to": None, "why": f} for f in best["fixes"]]
    else:                                                # the deterministic compile_spec page, same design document
        why = "agents off" if not ctx.enabled else (cands[-1]["blocking"][:4] if cands else "no model page")
        if cands:
            cache.drop("a5", k5)
        spec, flog = flow.fallback(st, h)
        overrides += flog
        page = validate_page.check(compile_spec.render(spec), spec)
        qa_res = measure(page["html"], spec) if not page["errors"] else None
        for _round in range(2):                          # repair what the browser measured, recheck
            c = classify(page, qa_res)
            if not (c["blocking"] or c["fix_motifs"]):
                break
            spec2, fix = qa_repair(spec, problems(qa_res))
            if not fix:
                break
            overrides += fix
            spec = spec2
            page = validate_page.check(compile_spec.render(spec), spec)
            qa_res = measure(page["html"], spec) if not page["errors"] else None
        c = classify(page, qa_res)
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
              "ledger": ctx.quota(sorted({m for t in trace for m in [t.get("model")] if m})),
              "ms": int((time.time() - t0) * 1000)}
    (od / "result.json").write_text(json.dumps({k: v for k, v in result.items() if k != "spec"}, indent=1, default=str),
                                    encoding="utf-8")
    return result


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
