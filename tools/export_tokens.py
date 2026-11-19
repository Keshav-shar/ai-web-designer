"""export_tokens.py - turn a lab run into the web app's theme (the lab is the design source; guardrails repair).

    python tools/export_tokens.py fixtures/lab_dreamy_full.json --theme light
    python tools/export_tokens.py <lab.json> [--theme auto|light|dark] [--heading "Family"] [--body "Family"]

Input: the output of `route_engine.py query "<q>" --lab --fam <family> --full` (log lines before the JSON are
skipped). Writes web/app/theme/tokens.css, web/app/theme/tokens.json and web/app/fonts.ts. Exits non-zero if any
text pair still fails WCAG after the guardrails, so a bad palette can never ship.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
import guardrails as g  # noqa: E402
from labio import load_lab_json  # noqa: E402

WEB = ROOT / "web"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lab_json")
    ap.add_argument("--theme", default="auto", choices=["auto", "light", "dark"])
    ap.add_argument("--heading")
    ap.add_argument("--body")
    a = ap.parse_args(argv)

    o = load_lab_json(Path(a.lab_json))
    p = o["payload"]
    v = p["vibe"] or {"name": p["family"], "cues": "", "effect": ""}
    over = []
    if a.theme != "auto":
        over.append({"token": "theme", "from": "auto", "to": a.theme, "why": "chosen at export (--theme)"})
    roles, derived, visuals, o_col = g.colour_roles(p["palette"]["swatches"], p["color_tokens"], a.theme)
    over += o_col
    f = o["fonts"]
    heading, body, italic, o_font = g.pick_fonts([s["name"] for s in f.get("shortlist", [])],
                                                 [s["name"] for s in f.get("body_cands", [])],
                                                 p["fonts"]["heading"]["family"], p["fonts"]["body"]["family"],
                                                 v["cues"], a.heading, a.body)
    over += o_font
    scale, o_scale = g.type_scale(p["fonts"]["tokens"], landing=True)
    over += o_scale
    report = g.contrast_report(roles)
    failing = [r for r in report if not r["pass"]]

    tokens = {"source": {"query": p["query"], "family": p["family"], "layout": p["layout"], "palette": p["palette"]["id"],
                         "lab_fonts": [p["fonts"]["heading"]["family"], p["fonts"]["body"]["family"]],
                         "pi_log": p.get("pi_log", [])},
              "vibe": v, "theme": a.theme, "color": roles, "derived": derived, "visuals": visuals,
              "type": scale, "fonts": {"heading": heading, "heading_italic": italic, "body": body,
                                       "heading_css": g.google_css(heading, italic), "body_css": g.google_css(body, False)},
              "contrast": report, "lab_contrast": p["contrast"], "overrides": over,
              "sections": p["sections"]}

    for r in report:
        print(f"  {r['pair']:<22} {r['ratio']:>5}  {'ok' if r['pass'] else 'FAIL'}")
    print(f"  {len(over)} override(s):")
    for x in over:
        print(f"    {x['token']}: {x['from']} -> {x['to']}  ({x['why']})")
    if failing:
        print("contrast still failing after guardrails - nothing written", file=sys.stderr)
        return 2
    from theme import write_theme
    write_theme(tokens)
    print(f"wrote theme: family {p['family']}  theme {a.theme}  heading {heading}{' (italic)' if italic else ''}  body {body}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
