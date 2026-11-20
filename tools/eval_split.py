"""eval_split.py - how well the worker's prompt split routes, on the taste catalogue's labelled queries (read-only).

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe tools\\eval_split.py [--router v1|v2]

Every category query in serpman's taste_catalog lists the vibes that suit it (r >= 2). Each split policy turns the
query into a vibe_query, the router picks a family, and we count:
  top-1   the routed family is an expected one
  top-3   an expected family is in the router's top 3
  +attr   top-1 again, with ", <product attribute>" appended to every query ("…, soft and chewy"): the shape of
          request that broke the Studio on 2026-11-21 (the old web split routed "soft and chewy" alone)
Policies: `split.py` (the worker's, the only one in production), `full prompt` (no split), and `old web split`
(the retired web/lib/split.ts rule, frozen here as the regression baseline).

Exit code 1 when split.py falls below FLOOR (the values measured when route_query shipped, router v1), so a
future change to the split has to keep or beat them. Nothing is written; the lab's pi cursor is not touched.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
from labio import lab_path  # noqa: E402

lab_path()
import context_clusters as cc  # noqa: E402  (serpman)
import route_engine as re_  # noqa: E402
import taste_catalog as tc  # noqa: E402
import palette_lab as pl  # noqa: E402

import split as S  # noqa: E402

FLOOR = {"top1": 0.679, "top3": 0.917, "attr": 0.688}       # split.py, router v1, 2026-11-21 (148/200/150 of 218)
ATTRS = ["soft and chewy", "fast and reliable", "warm and friendly", "simple and clean", "fresh every day",
         "bold and loud"]
OLD_CLAUSE = re.compile(r"(?:\b(?:feels?|feeling|looks?)\s+(?:like\s+)?|\bvibes?:?\s+|,\s*)([^,;]{3,80})", re.I)


def old_web_split(p: str) -> str:
    """The retired web/lib/split.ts fallback: catalogue words, else the clause after the first comma."""
    words = re.findall(r"[a-z0-9]+", p.lower())
    v = " ".join(dict.fromkeys(w for w in words if w in S.CATALOG["vibe_words"]))
    if not v:
        m = OLD_CLAUSE.search(p)
        v = m.group(1).strip(" .") if m else ""
    return v or p


POLICIES = {"split.py": lambda p: S.fallback(p)["vibe_query"], "full prompt": lambda p: p,
            "old web split": old_web_split}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--router", choices=("v1", "v2"), default="v1")
    a = ap.parse_args()
    ix, enc = re_.Index(), re_.TextEncoder(visual=False)
    P = pl.parse_params({})
    fv = {v.key: cc.slug(v.name) for v in tc.VIBES}
    Q = [(q, {fv[k] for k, r in v.vibes.items() if r >= 2}) for c in tc.CATEGORIES for v in c.values
         for q in (v.main, v.alt)]
    memo: dict[str, tuple[str, set[str]]] = {}

    def route(q: str) -> tuple[str, set[str]]:
        if q not in memo:
            r = (re_.route_v2(ix, enc, q, P["w"], None, re_.r2_opts(P), None, linking=False) if a.router == "v2"
                 else re_.route(ix, enc, q, P["w"]))
            memo[q] = (r["routed"], {f["fam"] for f in r["families"][:3]})
        return memo[q]

    print(f"{len(Q)} labelled catalogue queries, router {a.router}\n")
    print(f"{'policy':<15}{'top-1':>8}{'top-3':>8}{'+attr':>8}")
    res = {}
    for name, f in POLICIES.items():
        t1 = t3 = at = 0
        for i, (q, exp) in enumerate(Q):
            top, top3 = route(f(q))
            t1 += top in exp
            t3 += bool(exp & top3)
            at += route(f(f"{q}, {ATTRS[i % len(ATTRS)]}"))[0] in exp
        res[name] = {"top1": t1 / len(Q), "top3": t3 / len(Q), "attr": at / len(Q)}
        r = res[name]
        print(f"{name:<15}{r['top1']:>8.1%}{r['top3']:>8.1%}{r['attr']:>8.1%}")
    if a.router != "v1":
        print("\n(floor applies to router v1 only)")
        return 0
    low = [k for k, v in FLOOR.items() if round(res["split.py"][k], 3) < v]
    print("\nRESULT: " + ("split.py meets the floor " + str(FLOOR) if not low else f"split.py below the floor on {low}"))
    return 1 if low else 0


if __name__ == "__main__":
    sys.exit(main())
