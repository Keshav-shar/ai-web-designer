"""landing_fixture.py - record lab runs for the landing-page agent pipeline's offline tests.

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe tools\\landing_fixture.py ["query" ...]

For each query: route_engine.lab() as a preview (serve=0: the pi cursor never moves), plus every (fam, id) image
the run references, resolved to its local file and its CLIP text score. Written to fixtures/landing/<slug>.json, so
tests can build handoffs without loading CLIP (the images themselves stay in the corpus on D:).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
from labio import lab_path  # noqa: E402

lab_path()
import brief as B  # noqa: E402
import palette_lab as pl  # noqa: E402
import route_engine as re_  # noqa: E402

OUT = ROOT / "fixtures" / "landing"
QUERIES = ["neon synthwave music festival", "calm organic skincare brand", "retro 1976 analog synth and vinyl festival"]


def refs(o, acc):
    if isinstance(o, dict):
        if isinstance(o.get("fam"), str) and isinstance(o.get("id"), str):
            acc.add((o["fam"], o["id"]))
        for v in o.values():
            refs(v, acc)
    elif isinstance(o, list):
        for v in o:
            refs(v, acc)
    return acc


def main(qs):
    ix, enc = re_.Index(), re_.TextEncoder()
    L = re_.Lab(ix)
    score = B.clip_text_scores(enc, ix.E)
    OUT.mkdir(parents=True, exist_ok=True)
    for q in qs:
        P = pl.parse_params({"serve": "0"})
        o = re_.lab(ix, enc, L, q, P)
        if "error" in o:
            print(f"{q!r}: lab error {o['error']}")
            continue
        res, txt = {}, {}
        for fam, id_ in refs(o, set()):
            k = ix.key.get((fam, id_))
            if k is not None and Path(ix.dest[k]).exists():
                res[f"{fam}/{id_}"] = ix.dest[k]
                txt[f"{fam}/{id_}"] = round(float(score[k]), 4)
        slug = re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")[:48]
        f = OUT / f"{slug}.json"
        f.write_text(json.dumps({"q": q, "o": o, "resolve": res, "text": txt}, default=str), encoding="utf-8")
        print(f"wrote {f} ({len(res)} images, family {o['routed']})")


if __name__ == "__main__":
    main(sys.argv[1:] or QUERIES)
