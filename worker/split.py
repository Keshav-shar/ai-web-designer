"""split.py - prompt -> Split v1 {full_query, vibe_query, ...}. Same prompt and fallback as web/lib/split.ts."""
from __future__ import annotations

import json
import re
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
CATALOG = json.loads((CONTRACTS / "catalog.json").read_text(encoding="utf-8"))
SECTION_IDS = set(CATALOG["section_ids"])
CATEGORY_KEYS = {c["key"] for c in CATALOG["categories"]}


def system_prompt() -> str:
    t = (CONTRACTS / "prompts" / "split.md").read_text(encoding="utf-8")
    return (t.replace("{{FAMILIES}}", "\n".join(f"- {v['term']}: {v['name']}" for v in CATALOG["vibes"]))
             .replace("{{CATEGORIES}}", "\n".join(f"- {c['key']}: {c['name']}" for c in CATALOG["categories"]))
             .replace("{{SECTIONS}}", ", ".join(CATALOG["section_ids"])))


def fallback(prompt: str) -> dict:
    """No model: style words (from the vibe catalogue) form the vibe query; category from reserved words."""
    words = re.findall(r"[a-z0-9]+", prompt.lower())
    vibe = " ".join(dict.fromkeys(w for w in words if w in CATALOG["vibe_words"]))
    cat = next((c["key"] for c in CATALOG["categories"] if set(words) & set(c["tokens"])), None)
    if not vibe:                    # no catalogue style word: use the style clause ("..., hand-drawn and loud")
        m = STYLE_CLAUSE.search(prompt)
        vibe = m.group(1).strip(" .") if m else ""
    m = BRAND.search(prompt)
    return {"full_query": prompt.strip()[:300], "vibe_query": (vibe or prompt.strip())[:300],
            "category_hint": cat, "brand_name": m.group(1)[:80] if m else None, "audience": None,
            "must_sections": [], "source": "fallback"}


# "called Dew", "named Moss & Co" -> brand (capitalised words right after called/named); same regex in split.ts
BRAND = re.compile(r"\b(?:called|named)\s+([A-Z][\w&'.-]*(?:\s+(?:&\s+)?[A-Z][\w&'.-]*){0,3})")
# the look, when no catalogue word names it: after "feels (like)" / "looks (like)" / "vibe:" or the first comma
STYLE_CLAUSE = re.compile(r"(?:\b(?:feels?|feeling|looks?)\s+(?:like\s+)?|\bvibes?:?\s+|,\s*)([^,;]{3,80})", re.I)


def clean(d: dict, prompt: str) -> dict:
    fb = fallback(prompt)
    full = str(d.get("full_query") or "").strip()[:300] or fb["full_query"]
    vibe = str(d.get("vibe_query") or "").strip()[:300] or fb["vibe_query"]
    cat = d.get("category_hint") if d.get("category_hint") in CATEGORY_KEYS else None
    must = [s for s in (d.get("must_sections") or []) if isinstance(s, str) and s in SECTION_IDS][:8]
    brand = d.get("brand_name")
    aud = d.get("audience")
    return {"full_query": full, "vibe_query": vibe, "category_hint": cat,
            "brand_name": str(brand)[:80] if brand else None, "audience": str(aud)[:160] if aud else None,
            "must_sections": must, "source": "qwen"}


def split(prompt: str, qwen=None) -> dict:
    if qwen is None or not qwen.ok:
        return fallback(prompt)
    try:
        d = qwen.chat_json([{"role": "system", "content": system_prompt()},
                            {"role": "user", "content": f"Request: {prompt.strip()[:300]!r}"}],
                           model=qwen.split_model, max_tokens=400, temperature=0.1)
        return clean(d, prompt)
    except Exception:  # noqa: BLE001 - the split must never block a job
        return fallback(prompt)
