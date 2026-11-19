"""agent.py - Qwen writes the L2 sections one at a time inside the skeleton the brief defines.

Per section: one tightly scoped prompt (contracts/prompts/section.md + a JSON context), validate.check, one retry
with the errors fed back, then a deterministic fallback. nav / footer (L1) and the overlay (L3) are built by
assemble.py from the brief, so every page has the same reliable frame.
"""
from __future__ import annotations

import json
from html import escape
from pathlib import Path

import validate
from assets import page_assets

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
FRAME_IDS = {"nav", "footer", "overlay_fx"}           # built by assemble.py
VISUAL_SECTIONS = ["hero", "showcase", "features", "lookbook", "gallery", "how_it_works", "game_trailer",
                   "product_grid", "ingredients", "impact_stats"]


def title_of(sid: str) -> str:
    return sid.replace("_", " ").title().replace("Faq", "FAQ").replace("Cta", "CTA")


def content_sections(brief: dict) -> list[dict]:
    return [s for s in brief["sections"] if s["layer"] == "L2" or s["id"] == "announce_bar"
            if s["id"] not in FRAME_IDS]


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


def fallback(brief: dict, split: dict, sec: dict, images: list[dict]) -> str:
    """Plain, valid section in the page's own classes; copy says what belongs there rather than inventing it."""
    sid, brand = sec["id"], escape(split.get("brand_name") or "")
    what = escape(split["full_query"])
    img = (f'<img src="{images[0]["path"]}" alt="{escape(images[0].get("type") or "illustration")} artwork" '
           f'class="float w-full rounded-[2rem] object-cover aspect-[4/3]">') if images else ""
    if sid == "hero":
        return (f'<section id="hero" class="container-x grid gap-12 py-24 md:grid-cols-2 md:items-center md:py-32">'
                f'<div class="fade-up"><p class="eyebrow">{brand or escape(brief["taste"]["category_name"])}</p>'
                f'<h1 class="font-heading text-[length:var(--fs-7)] leading-[var(--lh-heading)] text-[var(--text)] '
                f'md:text-[length:var(--fs-8)]">{what}</h1>'
                f'<p class="mt-6 max-w-[66ch] text-[length:var(--fs-2)] text-[var(--text-muted)]">{escape(sec["purpose"])}.</p>'
                f'<div class="mt-10 flex flex-wrap gap-4"><a class="btn btn-primary" href="#cta_band">Get started</a>'
                f'<a class="btn btn-ghost" href="#features">See how it works</a></div></div>'
                f'<div class="relative"><div class="soft-glow" aria-hidden="true"></div>{img}</div></section>')
    if sid == "announce_bar":
        return (f'<section id="announce_bar" class="py-2 text-center text-[length:var(--fs-1)] bg-[var(--surface)] '
                f'text-[var(--text)]"><a href="#cta_band">{what} - <span class="underline">learn more</span></a></section>')
    if sid == "cta_band":
        return (f'<section id="cta_band" class="container-x py-24"><div class="glass px-8 py-16 text-center">'
                f'<h2 class="font-heading text-[length:var(--fs-6)] text-[var(--text)]">Ready when you are</h2>'
                f'<p class="mx-auto mt-4 max-w-[66ch] text-[var(--text-muted)]">{escape(sec["purpose"])}.</p>'
                f'<a class="btn btn-primary mt-8" href="mailto:hello@example.com">Get in touch</a></div></section>')
    cards = "".join(f'<div class="glass p-8"><h3 class="font-heading text-[length:var(--fs-4)] text-[var(--text)]">'
                    f'{title_of(sid)} {k}</h3><p class="mt-3 text-[var(--text-muted)]">Add the {k}{"st" if k == 1 else "nd" if k == 2 else "rd"} '
                    f'point for this section here.</p></div>' for k in (1, 2, 3))
    return (f'<section id="{sid}" class="container-x py-20"><p class="eyebrow">{title_of(sid)}</p>'
            f'<h2 class="font-heading text-[length:var(--fs-6)] text-[var(--text)]">{escape(sec["purpose"]).capitalize()}</h2>'
            f'{"<div class=\"mt-10\">" + img + "</div>" if img else ""}'
            f'<div class="mt-10 grid gap-6 md:grid-cols-3">{cards}</div></section>')


def generate(brief: dict, split: dict, qwen, layout_note: str | None = None, on_section=None) -> list[dict]:
    """-> [{id, html, fallback, errors}] in page order. on_section(result, i, n) is called after each one."""
    secs = content_sections(brief)
    imgs = plan_images(brief)
    out, prev = [], None
    for i, sec in enumerate(secs):
        allowed = {a["path"] for a in imgs.get(sec["id"], [])}
        res = {"id": sec["id"], "html": None, "fallback": False, "errors": []}
        if qwen is not None and qwen.ok:
            msgs = [{"role": "system", "content": system_prompt(brief, sec["id"])},
                    {"role": "user", "content": user_context(brief, split, sec, imgs.get(sec["id"], []), layout_note,
                                                             prev, i, len(secs))}]
            for attempt in range(2):
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
            res["html"], fb_errs = validate.check(fallback(brief, split, sec, imgs.get(sec["id"], [])), sec["id"], allowed)
            assert res["html"], f"fallback for {sec['id']} failed validation: {fb_errs}"
            res["fallback"] = True
        prev = res["html"]
        out.append(res)
        if on_section:
            on_section(res, i, len(secs))
    return out
