"""
build_evidence.py - the public /evidence page's data: measured values, comparisons and impacts from the pipeline.

    python tools/build_evidence.py            # -> web/content/evidence.generated.ts

Inputs (all local, nothing read from the DB):
    D:\\serpman_data\\evidence\\*.json          serpman lab export (evidence_export.py, read-only)
    out/_landing_live/*/result.json, out/_lab/*/result.json
                                              5-agent landing runs; only runs where a model actually answered count

Only aggregates and short labels reach the page: no image ids, file paths, key hashes or raw model output.
"""
from __future__ import annotations

import collections
import json
import os
import re
import statistics
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
SRC = Path(os.getenv("EVIDENCE_OUT", r"D:\serpman_data\evidence"))
OUT_DIRS = [ROOT / "out" / "_landing_live", ROOT / "out" / "_lab"]


def load(name: str):
    p = SRC / f"{name}.json"
    if not p.exists():
        raise SystemExit(f"missing {p}: run the lab's evidence_export.py first")
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------- WCAG helpers
def _lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hx: str) -> float:
    h = hx.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return round((la + 0.05) / (lb + 0.05), 2)


HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
# the same targets worker/guardrails.py pushes to (colour_roles / contrast_report)
CHECKS = {"--text": [("--bg", 7.0), ("--surface", 4.5)], "--text-muted": [("--bg", 4.5), ("--surface", 4.5)],
          "--accent": [("--on-accent", 4.5), ("--bg", 3.0)]}
PAIR_TARGET = {"accent/bg": 3.0}


# ---------------------------------------------------------------------------- sections
def funnel(F: dict, runs: list[dict]) -> dict:
    mean = lambda k: round(statistics.mean(r["counts"][k] for r in runs), 1) if runs else 0  # noqa: E731
    return {
        "corpus": [
            {"label": "Image and page hits claimed by search", "value": F["claims"]},
            {"label": f"Images kept in {F['families']} aesthetic families", "value": F["family_images"]},
            {"label": "Curated 'cream' layer the engine searches", "value": F["cream"]},
        ],
        "per_page": [
            {"label": "Images the lab hands forward", "value": mean("taken")},
            {"label": "In the design brief", "value": mean("in_brief")},
            {"label": "Placed on the page", "value": mean("on page")},
            {"label": "Kept as reference (guides layout / colour)", "value": mean("reference")},
        ],
        "cream_rule": F["cream_rule"],
        "runs": len(runs),
    }


def views(V: dict) -> dict:
    rows = [{"label": v["label"], "clip": v["clip"], "hit1": v["hit@1"], "purity": v["purity"]} for v in V["views"]]
    rows.sort(key=lambda r: -r["hit1"])
    return {"family": V["family"], "items": V["items"], "labels": V["labels"], "chance": V["chance"], "rows": rows}


def routing(C: dict) -> dict:
    v1, v2 = C["v1"], C["v2"]

    def top_share(w: dict, k: int = 5) -> float:
        n = sum(w.values())
        return round(sum(sorted(w.values(), reverse=True)[:k]) / n, 3) if n else 0.0

    return {"queries": C["queries"], "vibes": C["vibes"],
            "rows": [{"metric": "Top-1 family is an expected one", "v1": v1["top1"], "v2": v2["top1"]},
                     {"metric": "Expected family in top 3", "v1": v1["top3"], "v2": v2["top3"]},
                     {"metric": "Named vibe routes to itself", "v1": v1["self_route"], "v2": v2["self_route"]}],
            "families_used": {"v1": v1["families_used"], "v2": v2["families_used"]},
            "top5_share": {"v1": top_share(v1["wins"]), "v2": top_share(v2["wins"])}}


def text_filter(T: dict) -> dict:
    rows = [{"type": r["type"], "n": r["n"], "clip": r["clip_flag"], "pixel": r["pixel_flag"],
             "median": r["clip_q"][2], "q25": r["clip_q"][1], "q75": r["clip_q"][3]} for r in T["types"]]
    return {"threshold": T["threshold"], "images": T["images"], "pixel_rule": T["pixel_rule"], "rows": rows}


def contrast_runs(runs: list[dict]) -> dict:
    pairs = collections.OrderedDict()
    for r in runs:
        for c in r.get("contrast") or []:
            pairs.setdefault(c["pair"], []).append({"query": r["query"], "ratio": c["ratio"], "pass": bool(c["pass"])})
    rows = [{"pair": p, "target": PAIR_TARGET.get(p, 4.5), "points": pts, "min": min(x["ratio"] for x in pts)}
            for p, pts in pairs.items()]
    fails = [{"pair": p["pair"], "query": x["query"], "ratio": x["ratio"]} for p in rows for x in p["points"] if not x["pass"]]
    total = sum(len(p["points"]) for p in rows)
    return {"runs": len(runs), "rows": rows, "checks": total, "fails": fails}


def corrections(runs: list[dict]) -> list[dict]:
    """Colour overrides (OKLab lightness pushes) that fixed a failing pair. Before = the lab's own hex on the final
    palette, after = the shipped hex; each is measured on the token's binding check (the worst ratio / target)."""
    out = []
    for r in runs:
        col = r["colors"]
        for o in r.get("overrides") or []:
            tok, a, b = o.get("token"), o.get("from"), o.get("to")
            if tok not in CHECKS or not all(isinstance(x, str) and HEX.match(x) for x in (a, b)):
                continue
            checks = [(p, t, col[p]) for p, t in CHECKS[tok] if HEX.match(str(col.get(p, "")))]
            if not checks:
                continue
            p, t, against = min(checks, key=lambda c: contrast(a, c[2]) / c[1])
            before, after = contrast(a, against), contrast(b, against)
            if before >= t:
                continue                     # not a fix: re-derived (muted = mix) or polarity change, no failure
            out.append({"query": r["query"], "token": tok, "on": p, "target": t, "from": a.upper(), "to": b.upper(),
                        "against": against.upper(), "before": before, "after": after, "reached": after >= t - 0.01})
    out.sort(key=lambda x: x["before"])
    return out


REASONS = [  # (pattern in the bench's `why`, short label) - first match wins
    (r"already taken", "Duplicate of an earlier pick"),
    (r"baked-in text|CLIP reads", "Baked-in text"),
    (r"folder cap", "Folder cap (18 per brief)"),
    (r"file not found", "File missing"),
    (r"no compose template", "No section takes this image type"),
    (r"one central graphic", "Only one hero visual per page"),
    (r"already filled", "Every matching slot filled"),
]


def reason_of(why: str) -> str:
    for pat, label in REASONS:
        if re.search(pat, why or ""):
            return label
    return "Other"


def placement(runs: list[dict]) -> dict:
    rows = [{"query": r["query"], "family": r["family"],
             **{k: r["counts"].get(k, 0) for k in ("on page", "reference", "unused", "dropped")}} for r in runs]
    why = collections.Counter()
    for r in runs:
        for f in r["flow"]:
            if f["status"] in ("unused", "dropped"):
                why[(f["status"], reason_of(f["why"]))] += 1
    reasons = [{"status": s, "reason": l, "n": n} for (s, l), n in why.most_common()]
    return {"rows": rows, "reasons": reasons}


GATE_KINDS = [  # override token / reason -> what the code gate corrected in the model's output
    (r"\.pair$|4\.5:1", "Raised text contrast to 4.5:1"),
    (r"\.backing$|backing", "Added a backing plate on a busy zone"),
    (r"\.row$|cell already taken", "Moved off an occupied grid cell"),
    (r"col_span|needs ~\d+px", "Widened to fit the text on one line"),
    (r"cover text|cover image|motif", "Moved a motif off text or images"),
]


def gate() -> dict:
    runs = []
    for d in OUT_DIRS:
        for p in sorted(d.glob("*/result.json")):
            r = json.loads(p.read_text(encoding="utf-8"))
            srcs = [t.get("source") for t in r.get("trace", [])]
            if not any(s in ("model", "cache", "repaired") for s in srcs):
                continue                         # agents off: deterministic defaults, not evidence of the gate
            kinds = collections.Counter()
            for o in r.get("overrides", []):
                s = f"{o.get('token', '')} {o.get('why', '')}"
                kinds[next((l for pat, l in GATE_KINDS if re.search(pat, s)), "Other layout fix")] += 1
            qa = r.get("qa") or {}
            runs.append({"page_source": r.get("page_source"), "overrides": sum(kinds.values()),
                         "kinds": dict(kinds), "agents_from_model": sum(s in ("model", "cache") for s in srcs),
                         "qa_problems": {w: len(x.get("problems", [])) for w, x in qa.items()} or None})
    total = collections.Counter()
    for r in runs:
        total.update(r["kinds"])
    return {"runs": len(runs), "kinds": [{"kind": k, "n": n} for k, n in total.most_common()],
            "page_sources": dict(collections.Counter(r["page_source"] for r in runs)),
            "with_qa": sum(1 for r in runs if r["qa_problems"])}


def main() -> None:
    F, V, C, T, PL = load("funnel"), load("views"), load("coverage"), load("text_filter"), load("placement")
    runs = PL["runs"]
    data = {
        "funnel": funnel(F, runs),
        "views": views(V),
        "routing": routing(C),
        "text": text_filter(T),
        "contrast": contrast_runs(runs),
        "corrections": corrections(runs),
        "placement": placement(runs),
        "gate": gate(),
        "prompts": [r["query"] for r in runs],
    }
    meta = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "bench_runs": len(runs),
            "landing_runs": data["gate"]["runs"], "families_fingerprinted": 1}
    out = WEB / "content" / "evidence.generated.ts"
    body = (
        "// generated by tools/build_evidence.py from the serpman lab export - do not edit by hand\n"
        f"export const EVIDENCE_META = {json.dumps(meta)};\n"
        f"export const EVIDENCE = {json.dumps(data, ensure_ascii=False)};\n"
        "export type Evidence = typeof EVIDENCE;\n")
    out.write_text(body, encoding="utf-8")
    print(f"evidence: {len(runs)} bench runs, {data['gate']['runs']} landing runs, {len(body) // 1024} KB -> {out}")


if __name__ == "__main__":
    main()
