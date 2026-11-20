"""split.py - prompt -> Split v1 {full_query, vibe_query, ...}. The only implementation: the worker splits every job's
prompt itself and writes the result back to jobs.split (the web stores the prompt only).

vibe_query is the router's input and is always built by `route_query`: the look the request names (catalogue style
terms, the niche a domain word names, or the split model's style words) FOLLOWED BY the whole request. The subject
("banana bread", "skincare serum") carries most of CLIP's taste signal; a vibe query made of attribute words alone
("soft and chewy") routes to whichever family those words resemble. Measured with tools/eval_split.py.

`sanitize()` type-checks, cleans and caps the split model's output (untrusted text) before the engine uses it.
"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
CATALOG = json.loads((CONTRACTS / "catalog.json").read_text(encoding="utf-8"))
SECTION_IDS = set(CATALOG["section_ids"])
CATEGORY_KEYS = {c["key"] for c in CATALOG["categories"]}
MAX_PROMPT = 200          # the studio box, the API and the jobs.prompt check all use 200
MAX_QUERY = 300           # internal: the model may phrase full_query a little longer than the prompt


def normalize(text: object) -> str:
    """NFKC, drop control / zero-width / format characters, collapse whitespace (same as web/lib/prompt.ts)."""
    if not isinstance(text, str):
        return ""
    t = unicodedata.normalize("NFKC", text)
    t = "".join(" " if c.isspace() else c for c in t if unicodedata.category(c) not in ("Cc", "Cf") or c.isspace())
    return re.sub(r"\s+", " ", t).strip()


def _text(v: object, n: int) -> str | None:
    """A clean, capped string, or None for anything that is not a non-empty string/number."""
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        return None
    t = normalize(str(v))[:n].strip()
    return t or None


def system_prompt() -> str:
    t = (CONTRACTS / "prompts" / "split.md").read_text(encoding="utf-8")
    return (t.replace("{{FAMILIES}}", "\n".join(f"- {v['term']}: {v['name']}" for v in CATALOG["vibes"]))
             .replace("{{CATEGORIES}}", "\n".join(f"- {c['key']}: {c['name']}" for c in CATALOG["categories"]))
             .replace("{{SECTIONS}}", ", ".join(CATALOG["section_ids"])))


# "called Dew", "named Moss & Co" -> brand (capitalised words right after called/named)
BRAND = re.compile(r"\b(?:called|named)\s+([A-Z][\w&'.-]*(?:\s+(?:&\s+)?[A-Z][\w&'.-]*){0,3})")


VIBE_BY_KEY = {v["key"]: v for v in CATALOG["vibes"]}
CATEGORY_BY_KEY = {c["key"]: c for c in CATALOG["categories"]}


def niche_term(cat: str | None, words: list[str]) -> str | None:
    """'bakery' in the food category -> niche 'Bakery / cottagecore' -> its named vibe's search term."""
    for n in (CATEGORY_BY_KEY.get(cat) or {}).get("niches", []):
        if set(n.get("words", [])) & set(words):
            return VIBE_BY_KEY[n["vibe"]]["term"]
    return None


STYLE_TERMS = 2          # catalogue family terms put in front of the request (more dilute the subject)


def words_of(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def style_terms(words: list[str], cat: str | None) -> list[str]:
    """The look the request names in catalogue words: matched families' search terms (at most STYLE_TERMS), then
    the named vibe of a niche whose domain word appears ("bakery" -> cottagecore)."""
    keys = list(dict.fromkeys(k for w in words if w in CATALOG["vibe_words"] for k in CATALOG["vibe_words"][w]))
    terms = [VIBE_BY_KEY[k]["term"] for k in keys[:STYLE_TERMS]]
    nt = niche_term(cat, words)
    return list(dict.fromkeys(terms + ([nt] if nt else [])))


def route_query(full_query: str, terms: list[str]) -> str:
    """The router's input: style terms first, then the whole request, capped. Never drops the subject. A term the
    request already contains is still put in front: repeating the user's own style words weights them (measured by
    tools/eval_split.py: dropping the repeat lost 2 of 218 labelled queries)."""
    low = full_query.lower()
    terms = list(dict.fromkeys(x.strip() for x in terms if x and x.strip()))
    whole = next((t for t in terms if low in t.lower()), None)   # a model that already wrote the request in
    if whole:
        return whole[:MAX_QUERY]
    return " ".join(terms + [full_query])[:MAX_QUERY].strip() or full_query[:MAX_QUERY]


def category_of(words: list[str]) -> str | None:
    return next((c["key"] for c in CATALOG["categories"] if set(words) & set(c["tokens"])), None)


def fallback(prompt: str) -> dict:
    """No model: category from the categories' reserved words, look from the catalogue (style_terms), and the
    vibe query = route_query(those terms, the whole prompt)."""
    p = normalize(prompt)[:MAX_PROMPT] or "website"
    words = words_of(p)
    cat = category_of(words)
    m = BRAND.search(p)
    return {"full_query": p[:MAX_QUERY], "vibe_query": route_query(p, style_terms(words, cat)),
            "category_hint": cat, "brand_name": m.group(1)[:80] if m else None, "audience": None,
            "must_sections": [], "source": "fallback"}


def sanitize(d: object, prompt: str, source: str | None = None) -> dict:
    """Any dict-ish split from the split model -> a valid Split v1 (vibe_query rebuilt by route_query). Never raises."""
    d = d if isinstance(d, dict) else {}
    fb = fallback(prompt)
    must = d.get("must_sections")
    must = [s for s in must if isinstance(s, str) and s in SECTION_IDS][:8] if isinstance(must, list) else []
    cat = d.get("category_hint")
    src = source or (d.get("source") if d.get("source") in ("qwen", "fallback") else "fallback")
    full = _text(d.get("full_query"), MAX_QUERY) or fb["full_query"]
    look = _text(d.get("vibe_query"), MAX_QUERY)     # the model's style words; the request is appended below
    cat = cat if isinstance(cat, str) and cat in CATEGORY_KEYS else fb["category_hint"]
    return {"full_query": full,
            "vibe_query": route_query(full, [look] if look else style_terms(words_of(full), cat)),
            "category_hint": cat,
            "brand_name": _text(d.get("brand_name"), 80) or fb["brand_name"],
            "audience": _text(d.get("audience"), 160),
            "must_sections": list(dict.fromkeys(must)), "source": src}


def clean(d: dict, prompt: str) -> dict:
    return sanitize(d, prompt, source="qwen")


def split(prompt: str, qwen=None) -> dict:
    if qwen is None or not qwen.ok:
        return fallback(prompt)
    try:
        d = qwen.chat_json([{"role": "system", "content": system_prompt()},
                            {"role": "user", "content": f"Request: {normalize(prompt)[:MAX_PROMPT]!r}"}],
                           model=qwen.split_model, max_tokens=400, temperature=0.1)
        return clean(d, prompt)
    except Exception:  # noqa: BLE001 - the split must never block a job
        return fallback(prompt)
