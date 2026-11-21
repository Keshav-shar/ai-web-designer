"""schemas.py - the agents' output contracts (the design document A1..A4 write), built per run.

The legacy enums below (bands, groups, item kinds, primitives, ...) describe the deterministic fallback page that
compile_spec renders (flow.fallback); the agents themselves write the descriptive design document further down.

Every schema is *strict*: all properties required, additionalProperties false (Groq / Mistral strict json_schema need both,
Gemini responseJsonSchema accepts them). Numeric/length limits are NOT put in the provider schema (support varies);
`clamp_*` in the agents' semantic checks enforce them instead. `provider_schema()` strips them, `inline_refs()`
resolves $defs for providers that prefer flat schemas.
"""
from __future__ import annotations

import copy

PALETTE_ROLES = ["bg_primary", "bg_secondary", "text_top_heading", "text_subheading", "text_body", "text_inverse",
                 "accent_muted", "overlay_primary", "overlay_secondary", "cta_fill"]
TEXT_ROLES = ["text_top_heading", "text_subheading", "text_body", "text_inverse"]
SURFACE_ROLES = ["bg_primary", "bg_secondary", "cta_fill", "overlay_primary", "overlay_secondary", "accent_muted"]
# The five reference images A1 receives, in this order: role -> (label, image name, what it is for). One source of
# truth for the slice (image_roles), the header before each image part, the composite tiles and prompt a1.md.
IMAGE_ROLES = [
    ("background", "BACKGROUND_REF", "background-image",
     "backdrop reference: decide exact_adapt vs nuance_extract; never copy its subjects"),
    ("layout", "LAYOUT_REF", "layout-image",
     "a website screenshot: read only its structure (nav, hero arrangement, grid, cards), never its text or colours"),
    ("palette", "PALETTE_REF", "palette-image",
     "the colour source: allowed_hexes were measured from it; use it to judge which hex fits which role"),
    ("elements", "ELEMENTS_REF", "elements-image",
     "the primary central graphic: motifs, shapes and rhythm for design_elements"),
    ("typography", "TYPOGRAPHY_REF", "typography-image",
     "the family's type-specimen sheet: hierarchy, case, tracking, weight contrast (the font_pool lists its faces)"),
]
IMAGE_LABELS = [label for _, label, _, _ in IMAGE_ROLES]
ROLE_OF_LABEL = {label: (role, image, use) for role, label, image, use in IMAGE_ROLES}


def image_header(label: str, position: int | None, cluster: str = "", text_flag=None) -> str:
    """'[IMAGE 3 · palette: palette-image · PALETTE_REF] the colour source… | cluster: palette | baked-in text: no'."""
    role, image, use = ROLE_OF_LABEL[label]
    pos = f" {position}" if position else ""
    flag = "unknown" if text_flag is None else ("yes" if text_flag else "no")
    return f"[IMAGE{pos} · {role}: {image} · {label}] {use} | cluster: {cluster or '-'} | baked-in text: {flag}"
TEXTURES = ["grain", "stripes", "grid", "perspective_grid", "dots", "radial_glow", "mesh", "paper", "halftone",
            "scanlines", "none"]
BG_TREATMENT = ["photo_fill", "tinted", "masked_radial", "none"]
NAV = ["bar_left_logo", "centered_logo", "pill_floating", "minimal_split"]
HERO = ["split_left_text", "split_right_text", "centered", "full_bleed", "editorial_stack"]
INTRO = ["centered_statement", "two_column", "marquee_strip"]
CARDS = ["grid3", "bento", "staggered"]
DENSITY = ["airy", "balanced", "dense"]
CASES = ["none", "uppercase", "lowercase", "capitalize"]
TRACKING = ["-0.04em", "-0.02em", "0em", "0.04em", "0.08em", "0.14em", "0.2em"]
WEIGHTS = ["300", "400", "500", "600", "700", "800", "900"]
SHADOWS = ["none", "soft_drop", "hard_offset", "neon_glow", "outline"]
LINE_HEIGHTS = ["1.4", "1.5", "1.6", "1.7"]
PRIMITIVES = ["ribbon", "arch", "sunburst", "badge", "tape", "blob", "dots", "stripe_band", "squiggle", "star",
              "frame", "perspective_grid"]
BANDS = ["nav", "hero", "intro", "cards"]
BG_LAYER_KINDS = ["solid", "linear_gradient", "radial_glow", "stripes", "grid", "perspective_grid", "dots", "grain",
                  "mesh", "halftone", "scanlines", "paper", "image"]
POSITIONS = ["full", "top", "center", "bottom", "left", "right", "top_left", "top_right", "bottom_left",
             "bottom_right"]
BLENDS = ["normal", "multiply", "screen", "overlay", "soft-light"]
SCALES = ["fine", "medium", "bold"]
PADDING = ["tight", "regular", "loose"]
CONTENT_WIDTH = [1080, 1200, 1280]
GUTTER = [16, 24, 32]
ITEM_KINDS = ["logo", "nav_link", "cta", "eyebrow", "h1", "subheading", "centerpiece", "intro_heading",
              "intro_body", "card"]
# Five type levels (A1 assigns a face to each, A3 assigns a level to each item). Every element is optional except
# one h1: a design may have no logo, no CTA, no centerpiece, no intro, no cards, no decoration.
LEVELS = ["wordmark", "display", "subheading", "accent", "body"]
GROUPS = ["nav", "hero_text", "hero_media", "intro", "cards"]   # items that read as one block share a panel
GROUP_BAND = {"nav": "nav", "hero_text": "hero", "hero_media": "hero", "intro": "intro", "cards": "cards"}
ALIGN = ["left", "center", "right"]
GALIGN = ["start", "center", "end"]
BACKING = ["none", "solid", "frosted"]
HREFS = ["#top", "#hero", "#intro", "#cards"]
CARD_IDS = ["card_1", "card_2", "card_3", "card_4"]
CORNERS = ["tl", "tr", "bl", "br", "none"]
EDGES = ["top", "bottom", "left", "right", "none"]
LAYERS = ["z5", "z20"]
RELATIONS = ["in_free_area", "behind_element", "edge_of_element", "corner_of_container"]
INTENTS = ["none", "subtle", "rich"]
ADJ_OPS = ["pad_band", "band_gap", "align_group", "reserve_area"]
WORDMARK_SCALE = ["s", "m", "l", "xl"]

S = {"type": "string"}
N = {"type": "number"}
I = {"type": "integer"}
B = {"type": "boolean"}


def obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


def arr(items: dict) -> dict:
    return {"type": "array", "items": items}


def enum(values: list) -> dict:
    vals = list(dict.fromkeys(values))
    return {"type": "integer" if vals and all(isinstance(v, int) for v in vals) else "string", "enum": vals}


def ref(name: str) -> dict:
    return {"$ref": f"#/$defs/{name}"}


# --------------------------------------------------------------------------- the design document (A1..A4)
# Descriptive contracts: most values are free text written by the agents (what / where / why), modelled on a
# designer's brief. Only what code must check stays strict: ids, enums code renders from, hexes and font names
# (validated and snapped by code, flow.normalize_doc), the copy and its kinds.
PALETTE_GROUPS = ["text_color", "muted_accent_color", "background_element_color", "overlay_elements_color"]
SECTION_ROLES = ["nav", "hero", "intro", "feature", "cards", "gallery", "quote", "cta_band", "footer", "other"]
COPY_KINDS = ["logo", "nav_link", "cta", "eyebrow", "h1", "h2", "h3", "paragraph", "label", "quote", "stat",
              "list_item", "caption", "card"]
Z_LAYERS = [0, 5, 10, 20, 50]
DECOR_KINDS = ["svg", "css"]
EXTRA_HEXES = 4                       # colours A1 may add beyond the measured ones (logged)


def a1() -> dict:
    """A1 - the visual design document, written from the five reference images."""
    entry = obj({"name": S, "hex": S, "usage": S})
    level = {"family": S, "weight": enum(WEIGHTS), "case": enum(CASES), "letter_spacing": S, "italic": B,
             "classification": S, "visual_traits": S, "reference_style": S, "size_css": S, "line_height": S}
    el = obj({"id": S, "what": S, "where": S})
    return obj({
        "design_system_name": S,
        "aesthetic_direction": S,
        "query_context": S,
        "color_palette_distribution": obj({g: arr(entry) for g in PALETTE_GROUPS}),
        "role_map": obj({r: S for r in PALETTE_ROLES}),
        "typography": obj({
            "wordmark": obj(level), "display": obj({**level, "shadow_treatment": enum(SHADOWS)}),
            "subheading": obj(level), "accent": obj(level), "body": obj(level), "text_treatment_rules": S}),
        "background_layer": obj({
            "alignment_mode": enum(["exact_adapt", "nuance_extract"]), "use_background_image": B,
            "treatment": enum(BG_TREATMENT), "ignored_irrelevant_subjects": arr(S), "base_surface": S,
            "elements": arr(el)}),
        "centerpiece": obj({"use": B, "description": S, "where": S}),
        "midground_decor": arr(el),
        "foreground_overlays": arr(el),
        "content_sections": arr(obj({"section_id": S, "role": enum(SECTION_ROLES), "where": S, "what": arr(S)})),
        "composition_and_overlap_rules": obj({
            "alignment_grid": S, "permitted_overlaps": arr(obj({"a": S, "b": S, "why": S})),
            "prohibited_overlaps": arr(S)}),
        "layout_spec": obj({"nav": enum(NAV), "hero": enum(HERO), "intro": enum(INTRO), "cards": enum(CARDS),
                            "density": enum(DENSITY), "notes": S}),
        "strategic_cards": arr(obj({"card_id": enum(CARD_IDS), "tag": S, "heading": S, "body": S,
                                    "accent_color_key": enum(PALETTE_ROLES)})),
    })


def a2(section_ids: list[str], element_ids: list[str], colors: list[str]) -> dict:
    """A2 - the buildable layout plan for A1's outline."""
    return {**obj({"layout_plan": obj({
        "canvas": obj({"content_width_px": I, "gutter_px": I, "canvas_use": S}),
        "sections": arr(obj({"section_id": ref("section"), "layout": S, "size": S, "surface": ref("color"),
                             "responsive": S})),
        "layers": arr(obj({"element_id": ref("element"), "z": enum(Z_LAYERS), "anchor": ref("section"),
                           "placement": S, "notes": S})),
    })}), "$defs": {"section": enum(section_ids), "element": enum(element_ids or [""]), "color": enum(colors)}}


def a3(section_ids: list[str], colors: list[str]) -> dict:
    """A3 - the words, their kinds and hierarchy levels, and each section's colours."""
    return {**obj({"copy": obj({
        "brand": S,
        "items": arr(obj({"item_id": S, "section_id": ref("section"), "kind": enum(COPY_KINDS),
                          "level": enum(LEVELS), "text": S, "href": S, "card_id": enum([""] + CARD_IDS)})),
        "section_colors": arr(obj({"section_id": ref("section"), "surface": ref("color"), "text": ref("color"),
                                   "heading": ref("color"), "accent": ref("color")})),
    })}), "$defs": {"section": enum(section_ids), "color": enum(colors)}}


def a4(element_ids: list[str]) -> dict:
    """A4 - an SVG or CSS recipe for each decorative element of the plan."""
    return {**obj({"decor": obj({
        "intent": enum(INTENTS),
        "assets": arr(obj({"element_id": ref("element"), "kind": enum(DECOR_KINDS), "svg": S, "css": S,
                           "anchor": S, "placement": S, "opacity": N, "notes": S})),
    })}), "$defs": {"element": enum(element_ids or [""])}}


# --------------------------------------------------------------------------- helpers
STRIP = {"minLength", "maxLength", "minimum", "maximum", "minItems", "maxItems", "pattern", "format",
         "exclusiveMinimum", "exclusiveMaximum", "multipleOf"}


def provider_schema(schema: dict) -> dict:
    def walk(x):
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items() if k not in STRIP}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    return walk(schema)


def inline_refs(schema: dict) -> dict:
    defs = schema.get("$defs", {})

    def walk(x):
        if isinstance(x, dict):
            if "$ref" in x:
                return walk(copy.deepcopy(defs[x["$ref"].split("/")[-1]]))
            return {k: walk(v) for k, v in x.items() if k != "$defs"}
        if isinstance(x, list):
            return [walk(v) for v in x]
        return x
    return walk(schema)


def strict_problems(schema: dict) -> list[str]:
    """Strict-mode lint: every object lists all properties as required and forbids extras."""
    out = []

    def walk(x, path):
        if isinstance(x, dict):
            if x.get("type") == "object":
                props = x.get("properties", {})
                if set(x.get("required", [])) != set(props):
                    out.append(f"{path}: required != properties")
                if x.get("additionalProperties") is not False:
                    out.append(f"{path}: additionalProperties must be false")
            for k, v in x.items():
                walk(v, f"{path}/{k}")
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
    walk(schema, "#")
    return out
