"""parity_check.py - does the public Studio pipeline pick and build what the router lab does?

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe tools\\parity_check.py "neon synthwave music festival" [--vibe "..."]

Both paths run in one process at the same pi cursor (previews: nothing is advanced) with the baseline controls:
  lab path     route_engine.lab(query)                      = the lab's step 1 at "Reset to baseline", v1 tab
  studio path  worker Engine.recipe(prompt, split)          = what worker.py run does for a job (serve=False here)
then both through the landing handoff and the agent pipeline with agents OFF (deterministic, no model calls).

1. Code-path parity: both get the same vibe query -> picks, handoffs and landing pages must be identical.
2. Input difference: the Studio routes on the worker split's vibe_query (style terms + the whole prompt), the lab on
   the raw text you type; this part shows what that changes for the prompt (pass --vibe to force a vibe query).
Remaining differences by design: each Studio job advances pi (variety); custom lab controls don't apply to the
Studio (baseline). Exit code 0 = identical code paths.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
import worker  # noqa: E402  (loads worker/.env; nothing below makes a network or model call)
from landing import handoff as LH, pipeline as LP  # noqa: E402
from split import fallback  # noqa: E402

OUT = ROOT / "out" / "_parity"


def picks(o: dict) -> dict:
    P = o["params"]
    bg = (o["bg"].get(P["bg_use"]) or {}).get("chosen") or {}
    el = o.get("el") or {}
    ref = lambda c: f"{c['fam']}/{c['id']}" if c else None  # noqa: E731
    return {"family": o["routed"], "layout": ref(o["layout"]), "palette": ref(o["palette"]["chosen"]),
            "palette roles": tuple(sorted((k, v["hex"]) for k, v in o["roles"][o["roles"]["active"]]["roles"].items())),
            "background": ref(bg), "hero ref": ref((el.get("hero") or {}).get("chosen")),
            "central graphics": tuple(ref(c) for c in (el.get("central") or {}).get("picks", [])),
            "fonts": (o["fonts"].get("heading", {}).get("name"), o["fonts"].get("body", {}).get("name")),
            "typography sheet": ref(((o.get("typography") or {}).get("sheets") or [None])[0]),
            "pi before": o["pi"]["before"]["cursor"]}


def build(eng, o: dict, split: dict, name: str) -> tuple[dict, str]:
    brief, files = worker.build_brief(o, query=split["full_query"], split=split,
                                      sections_src=worker.prompt_context(eng.enc, split["full_query"]),
                                      resolve=eng.resolve, text_lines=eng.text_lines)
    h = LH.build(o, split, brief, files, theme="auto", resolve=eng.resolve, text_lines=eng.text_lines)
    r = LP.run(h, enabled=False, out_dir=OUT / name, qa=False, log=lambda *a: None)
    html = (Path(r["out"]) / "index.html").read_text(encoding="utf-8")
    return h, hashlib.sha256(html.encode()).hexdigest()[:16]


def compare(a: dict, b: dict, la: str, lb: str) -> int:
    diffs = 0
    w = max(len(k) for k in a)
    for k in a:
        same = a[k] == b[k]
        diffs += not same
        print(f"  {'same' if same else 'DIFF':<4}  {k:<{w}}  {a[k]!s:.70}" + ("" if same else f"\n        {'':<{w}}  {lb}: {b[k]!s:.70}"))
    return diffs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prompt")
    ap.add_argument("--vibe", help="force a vibe_query (default: the worker's split, worker/split.py)")
    a = ap.parse_args()
    eng = worker.Engine()
    split = fallback(a.prompt)
    if a.vibe:
        split["vibe_query"] = a.vibe
    vibe = split["vibe_query"]
    P = eng.pl.parse_params({"serve": "0"})

    print(f"\n1. code-path parity on the same vibe query: {vibe!r}")
    o_lab = eng.re.lab(eng.ix, eng.enc, eng.L, vibe, P)
    o_st, _, _ = eng.recipe(a.prompt, split, None, "auto", serve=False)
    d = compare(picks(o_lab), picks(o_st), "lab", "studio")
    lab_split = {**split, "vibe_query": vibe}
    h1, p1 = build(eng, o_lab, lab_split, "lab")
    h2, p2 = build(eng, o_st, split, "studio")
    same_h = [(k, v["id"]) for k, v in h1["images"].items()] == [(k, v["id"]) for k, v in h2["images"].items()] \
        and h1["enums"] == h2["enums"]
    print(f"  {'same' if same_h else 'DIFF':<4}  handoff (5 role images + allowed hexes / fonts)")
    print(f"  {'same' if p1 == p2 else 'DIFF':<4}  landing page with agents off (sha256 {p1} vs {p2})")
    d += (not same_h) + (p1 != p2)

    print(f"\n2. input difference: the lab routes on the raw prompt {a.prompt!r}, the Studio on {vibe!r}")
    if vibe.strip().lower() == a.prompt.strip().lower():
        print("  same text: no difference")
    else:
        o_raw = eng.re.lab(eng.ix, eng.enc, eng.L, a.prompt, P)
        compare(picks(o_raw), picks(o_st), "lab (raw prompt)", "studio")
        print("  (expected: the split puts catalogue style terms in front of the prompt; type the vibe text in the lab "
              "to see exactly what the Studio sees)")

    print("\nby design: each Studio job advances the pi cursor (the previews above didn't); the Studio uses the baseline "
          "controls, not the ones set in your lab browser.")
    print(f"pages: {OUT / 'lab'} and {OUT / 'studio'}")
    print("RESULT: " + ("identical code paths" if not d else f"{d} difference(s) on the same input: investigate"))
    return 0 if not d else 1


if __name__ == "__main__":
    sys.exit(main())
