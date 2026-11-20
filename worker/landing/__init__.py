"""landing - the 5-agent thematic landing-page pipeline (lab picks -> one landing page: nav, hero, intro, 3 cards).

    handoff   lab run -> facts + enums + labelled reference images (no model)
    A1  Gemini (multimodal)  visual deconstruction + palette/font role assignment from enums + cards
    A2  Groq gpt-oss         wireframe_grid (z-0 background layers, bands, safe boxes, negative space)
    A3  Groq gpt-oss         content_layer (z-10 grid placements, copy, contrast pairs from an enum)
    A4  Groq Qwen (vision)   overlay_layer (z-5 / z-20 motifs; code enforces the overlap laws)
    A5  Gemini               HTML/CSS compile; code re-wraps, checks conformance; compile_spec is the fallback

Principles: a blackboard with declared read/write sets (state.py), references instead of payloads, option sets
built by code and enforced by strict schemas, geometry by intent and boxes by code (spatial.py), outputs cached by
input hash (cache.py), header-driven pacing and a daily quota ledger (budget.py). Every agent has a deterministic
default (defaults.py), so the pipeline always produces a page, with or without keys.
"""
PROMPT_VERSION = "landing-v1"
