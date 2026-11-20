"""export_catalog.py - the taxonomy the worker's prompt split uses (worker/split.py), from serpman's taste_catalog.

    python tools/export_catalog.py      # writes contracts/catalog.json (+ the shared component CSS into web/app/theme)

The web never splits prompts (the worker does and writes the split back to the job), so no catalogue copy or split
prompt goes to web/.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "worker"))
from labio import lab_path  # noqa: E402

lab_path()
import section_plan as sp  # noqa: E402
import taste_catalog as tc  # noqa: E402

STOP = set("a an and or the of with for in on to by from website design style ui app page landing site web feel feels "
           "like look looks vibe vibes based inspired".split())


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40]


def main() -> None:
    reserved = set().union(*(c.tokens for c in tc.CATEGORIES))
    vocab: dict[str, list[str]] = {}
    for v in tc.VIBES:
        for w in re.findall(r"[a-z0-9]+", f"{v.name} {v.term}".lower()):
            if w not in STOP and w not in reserved and len(w) > 2:
                vocab.setdefault(w, []).append(v.key)
    out = {
        "version": 1,
        "vibes": [{"key": v.key, "family": slug(v.name), "name": v.name, "term": v.term, "cues": v.cues} for v in tc.VIBES],
        "categories": [{"key": c.key, "name": c.name, "tokens": sorted(c.tokens),
                        # `vibe` = the niche's named (r=3) vibe key: what a domain-only prompt ("bakery") should look like
                        "niches": [{"name": x.name, "cues": x.cues,
                                    "words": sorted({w for w in re.findall(r"[a-z]+", x.name.lower())
                                                     if len(w) > 3 and w not in STOP}),
                                    "vibe": max(x.vibes, key=x.vibes.get)} for x in c.values]} for c in tc.CATEGORIES],
        "vibe_words": dict(sorted(vocab.items())),
        "section_ids": sorted(sp.SECTIONS),
    }
    text = json.dumps(out, indent=1)
    (ROOT / "contracts" / "catalog.json").write_text(text, encoding="utf-8")
    if (ROOT / "web").exists():
        (ROOT / "web" / "app" / "theme").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "contracts" / "site-components.css", ROOT / "web" / "app" / "theme" / "site-components.css")
    print(f"catalog: {len(out['vibes'])} vibes, {len(out['categories'])} categories, "
          f"{len(out['vibe_words'])} vibe words, {len(out['section_ids'])} section ids")


if __name__ == "__main__":
    main()
