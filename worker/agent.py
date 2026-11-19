"""agent.py - who writes the sections.

SECTION_MODE=compose (default): compose.py builds every section from the lab's design + the family's folder
sections, no model involved.
SECTION_MODE=qwen: Qwen writes each L2 section from one tightly scoped prompt (contracts/prompts/section.md + a
JSON context), validate.check, one retry with the errors fed back; a section that still fails uses the composed one.
nav / footer (L1) and the overlay (L3) are always built by assemble.py from the brief.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import compose
import validate
from assets import page_assets

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
FRAME_IDS = {"nav", "footer", "overlay_fx"}           # built by assemble.py
VISUAL_SECTIONS = ["hero", "showcase", "features", "lookbook", "gallery", "how_it_works", "game_trailer",
                   "product_grid", "ingredients", "impact_stats"]


def title_of(sid: str) -> str:
    return sid.replace("_", " ").title().replace("Faq", "FAQ").replace("Cta", "CTA")


content_sections = compose.content_sections


def section_mode(qwen) -> str:
    return "qwen" if os.getenv("SECTION_MODE", "compose") == "qwen" and qwen is not None and qwen.ok else "compose"


def plan_images(brief: dict) -> dict[str, list[dict]]:
    """primary central graphic -> hero; supporting ones -> the next visual sections in page order."""
    central = [a for a in page_assets(brief) if a["role"] == "central"]
    primary = [a for a in central if "primary" in (a.get("note") or "")] or central[:1]
    rest = [a for a in central if a not in primary]
    ids = [s["id"] for s in content_sections(brief)]
    plan: dict[str, list[dict]] = {sid: [] for sid in ids}
    if "hero" in plan and primary:
        plan["hero"] = primary[:1]
    for sid in [s for s in VISUAL_SECTIONS if s in plan and s != "hero"]:
        if not rest:
            break
        plan[sid] = [rest.pop(0)]
    return plan


def system_prompt(brief: dict, sid: str) -> str:
    t = (CONTRACTS / "prompts" / "section.md").read_text(encoding="utf-8")
    top = max(int(k.split("-")[-1]) for k in brief["tokens"]["type"] if k.startswith("--fs-"))
    ta = brief["taste"]
    return (t.replace("{{SECTION_ID}}", sid).replace("{{TOP}}", str(top))
             .replace("{{VIBE_NAME}}", brief["vibe"]["name"]).replace("{{VIBE_CUES}}", brief["vibe"]["cues"])
             .replace("{{NICHE}}", ta.get("niche") or ta["category_name"]).replace("{{NICHE_CUES}}", ta.get("niche_cues") or "")
             .replace("{{AVOID}}", ", ".join(ta["avoid"]) or "nothing specific")
             .replace("{{ALIGN}}", brief["typography"].get("alignment", "left")))


def user_context(brief: dict, split: dict, sec: dict, images: list[dict], layout_note: str | None,
                 prev_html: str | None, i: int, n: int) -> str:
    ctx = {
        "site": {"what": split["full_query"], "brand": split.get("brand_name"), "audience": split.get("audience")},
        "section": {"id": sec["id"], "purpose": sec["purpose"], "position": f"{i + 1} of {n}"},
        "page_sections": [s["id"] for s in content_sections(brief)],
        "theme_variables": sorted(list(brief["tokens"]["color"]) + list(brief["tokens"]["derived"])
                                  + [f"--visual-{k + 1}" for k in range(len(brief["typography"].get("visuals", [])))]),
        "type_roles": brief["typography"]["roles"],
        "images you may use": [{"src": a["path"], "what": f"{a.get('type') or a['cluster']} ({a.get('note')})"} for a in images],
        "layout_reference_structure": layout_note or "not available: use a clean, generous, centred-to-split rhythm",
        "previous_section_html": (prev_html or "")[:1800] or None,
    }
    return json.dumps(ctx, indent=1)



def generate(brief: dict, split: dict, qwen, layout_note: str | None = None, on_section=None,
             copy: dict | None = None) -> list[dict]:
    """-> [{id, html, fallback, errors, source}] in page order. on_section(result, i, n) after each one."""
    if section_mode(qwen) == "compose":
        return compose.compose(brief, split, copy, on_section)
    composed = {s["id"]: s["html"] for s in compose.compose(brief, split, copy)}
    secs = content_sections(brief)
    imgs = plan_images(brief)
    out, prev = [], None
    for i, sec in enumerate(secs):
        allowed = {a["path"] for a in imgs.get(sec["id"], [])}
        res = {"id": sec["id"], "html": None, "fallback": False, "errors": [], "source": "qwen"}
        msgs = [{"role": "system", "content": system_prompt(brief, sec["id"])},
                {"role": "user", "content": user_context(brief, split, sec, imgs.get(sec["id"], []), layout_note,
                                                         prev, i, len(secs))}]
        for _attempt in range(2):
            try:
                reply = qwen.chat(msgs, max_tokens=3500, temperature=0.7)
            except Exception as e:  # noqa: BLE001
                res["errors"].append(f"model call failed: {e}"[:300])
                break
            html, errs = validate.check(reply, sec["id"], allowed)
            if html:
                res["html"] = html
                break
            res["errors"] += errs
            msgs += [{"role": "assistant", "content": reply[:6000]},
                     {"role": "user", "content": "Your section was rejected by the checker:\n- " + "\n- ".join(errs)
                                                 + "\nReturn the corrected <section> only."}]
        if res["html"] is None:
            res.update(html=composed[sec["id"]], fallback=True, source="compose")
        prev = res["html"]
        out.append(res)
        if on_section:
            on_section(res, i, len(secs))
    return out
