"""python worker/test_compose.py - every section id composes valid, placeholder-free HTML for every category."""
import copy
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import compose  # noqa: E402

ROOT = HERE.parent
CATALOG = json.loads((ROOT / "contracts" / "catalog.json").read_text(encoding="utf-8"))
BRIEF = json.loads((ROOT / "fixtures" / "brief_dreamy.json").read_text(encoding="utf-8"))
BAD = ("add the", "lorem", "[placeholder]", "todo", "xxx")


def brief_with(category: str, align: str, all_sections: bool) -> dict:
    b = copy.deepcopy(BRIEF)
    b["taste"]["category"] = category
    b["typography"]["alignment"] = align
    if all_sections:
        b["sections"] = [{"id": s, "layer": "L2", "purpose": s} for s in CATALOG["section_ids"]
                         if s not in ("nav", "footer", "overlay_fx", "cookie_consent", "toasts_modals")]
    # fake folder images of every type, some with text
    types = compose.HERO_TYPES + compose.SCREEN_TYPES + compose.GALLERY_TYPES + compose.LOGO_TYPES + ["icons"]
    b["assets"] += [{"ref_id": f"{i:012d}", "role": "section", "fam": "x", "id": f"{i}.jpg", "cluster": t, "type": t,
                     "note": "folder section", "path": f"assets/{i:012d}.webp", "text": i % 3 == 0}
                    for i, t in enumerate(types * 2)]
    return b


def run() -> int:
    fails = 0
    split = {"full_query": "a natural wine bar in Lisbon, hand-drawn and loud", "vibe_query": "hand-drawn loud",
             "brand_name": None}
    for cat in [c["key"] for c in CATALOG["categories"]]:
        for align in ("center", "left"):
            b = brief_with(cat, align, all_sections=True)
            try:
                out = compose.compose(b, split)
            except Exception as e:  # noqa: BLE001
                print(f"FAIL {cat}/{align}: {e}")
                fails += 1
                continue
            for s in out:
                low = s["html"].lower()
                hit = [w for w in BAD if w in low]
                if hit:
                    print(f"FAIL {cat}/{align}/{s['id']}: placeholder text {hit}")
                    fails += 1
            hero = next(s for s in out if s["id"] == "hero")["html"]
            texty = [a["path"] for a in b["assets"] if a.get("text")]
            if any(p in hero for p in texty):
                print(f"FAIL {cat}/{align}: hero uses an image with baked-in text")
                fails += 1
    # the About copy overrides
    about = json.loads((ROOT / "contracts" / "about_copy.json").read_text(encoding="utf-8"))
    b = brief_with("devsaas", "center", all_sections=False)
    b["sections"] = [{"id": s, "layer": "L2", "purpose": s} for s in ("hero", "how_it_works", "showcase", "faq", "cta_band")]
    out = compose.compose(b, {"full_query": "serpman studio", "vibe_query": "dreamy", "brand_name": "serpman studio"}, about)
    if "Describe a site. Get its taste." not in out[0]["html"] or 'href="#studio"' not in out[0]["html"]:
        print("FAIL about: hero copy override not applied")
        fails += 1
    print("compose:", "OK" if not fails else f"{fails} failure(s)",
          f"({len(CATALOG['categories'])} categories x 2 alignments x {len(CATALOG['section_ids']) - 5} sections + about)")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run())
