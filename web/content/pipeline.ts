import { EVIDENCE } from "@/content/evidence.generated";

/**
 * Copy and data for the studio's pipeline film (components/pipeline). Numbers come from the measured evidence
 * export; colours are sampled from the four reference images (Pillow quantize) and named by hand.
 * Copy rule: frame every stage as specialisation and contextual matching, never as loss.
 */

const corpus = EVIDENCE.funnel.corpus;

export const FUNNEL = [
  { value: corpus[0].value, label: "Public design references gathered by search", short: "gathered by search" },
  { value: corpus[1].value, label: "Specialised into 39 aesthetic families", short: "in 39 aesthetic families" },
  { value: corpus[2].value, label: "Defining cream layer the engine routes through", short: "cream layer" },
] as const;

export const fmt = (n: number) => Math.round(n).toLocaleString("en-US");

export type CaptionTag = "corpus" | "taste" | "agents" | "code" | "result";
export const TAG_LABEL: Record<CaptionTag, string> = {
  corpus: "Corpus", taste: "Taste", agents: "Agents", code: "Code", result: "Result",
};

export type Beat = { at: number; tag: CaptionTag; text: string };
export type SceneCopy = { id: string; act: 0 | 1 | 2; title: string; ms: number; beats: Beat[] };

export const ACTS = ["Core engine", "One query", "The page"] as const;

export const SCENES: SceneCopy[] = [
  { id: "serp", act: 0, title: "SERP engine", ms: 6500, beats: [
    { at: 0, tag: "corpus", text: "The SERP engine fans one idea out into hundreds of searches across public design sites." },
    { at: 0.5, tag: "corpus", text: "It starts from real, published design: references people made, not a model's defaults." },
  ] },
  { id: "pool", act: 0, title: "Reference pool", ms: 5500, beats: [
    { at: 0, tag: "corpus", text: `${fmt(FUNNEL[0].value)} references land in one pool. Breadth comes first.` },
    { at: 0.5, tag: "corpus", text: "A wide pool means taste comes from a corpus, not from one model's habits." },
  ] },
  { id: "cluster", act: 0, title: "Clustering", ms: 6500, beats: [
    { at: 0, tag: "taste", text: "Look-alikes cluster together, and every cluster joins one of 39 aesthetic families." },
    { at: 0.5, tag: "taste", text: "Each style gets its own shelf, so no single look drowns out the other 38." },
  ] },
  { id: "clip", act: 0, title: "CLIP taste selection", ms: 7500, beats: [
    { at: 0, tag: "taste", text: "CLIP scores every image against its family and keeps the most representative: high-profile, not average." },
    { at: 0.55, tag: "taste", text: "Hero art is checked for baked-in text, so pages never inherit someone else's words." },
  ] },
  { id: "dock", act: 1, title: "Core engine", ms: 4500, beats: [
    { at: 0, tag: "taste", text: "Zoom out: that taste layer is the Core Engine, built offline, once, with zero generative AI." },
  ] },
  { id: "query", act: 1, title: "User query", ms: 5000, beats: [
    { at: 0, tag: "taste", text: "A visitor types one sentence." },
    { at: 0.5, tag: "taste", text: "It is split into what the site is and how it should feel, and the feeling picks one of 39 families." },
  ] },
  { id: "refs", act: 1, title: "References out", ms: 5500, beats: [
    { at: 0, tag: "taste", text: "The engine hands back five labelled references: typography, background, layout, elements, palette." },
    { at: 0.5, tag: "taste", text: "Every later choice traces back to a real image, not a mood guessed from the prompt." },
  ] },
  { id: "attach", act: 1, title: "Brief to A1", ms: 4500, beats: [
    { at: 0, tag: "agents", text: "The query and its references travel together as one brief." },
    { at: 0.45, tag: "agents", text: "Only this agent looks at pictures; every later stage works from words it can be held to." },
  ] },
  { id: "breakdown", act: 1, title: "Component segregation", ms: 9500, beats: [
    { at: 0, tag: "agents", text: "A1 segregates each reference into components: type levels, background, centerpiece, decor, sections." },
    { at: 0.4, tag: "agents", text: "Every colour gets a name and a job: Marigold is the inner ribbon stripe and the CTA glow." },
    { at: 0.72, tag: "agents", text: "Components are described, never copied: no text or watermark leaves a reference." },
  ] },
  { id: "nonvlm", act: 2, title: "Non-VLM pipeline", ms: 8500, beats: [
    { at: 0, tag: "agents", text: "Text-only agents build on one shared document: A2 lays it out, A3 writes the copy, A4 draws the decor." },
    { at: 0.42, tag: "agents", text: "Each owns its part and hands it on; none rewrites another's decisions." },
    { at: 0.7, tag: "code", text: "Code, not a model, checks the facts: palette hexes, real fonts, contrast, ids, safe SVG." },
  ] },
  { id: "layers", act: 2, title: "Layer wrapping", ms: 7500, beats: [
    { at: 0, tag: "code", text: "The page is planned as layers: backdrop, decor under content, text and UI, foreground accents, grain." },
    { at: 0.55, tag: "code", text: "Decoration sits behind text by design, so nothing fights the words when the layers wrap." },
  ] },
  { id: "compose", act: 2, title: "A5 composes", ms: 7500, beats: [
    { at: 0, tag: "result", text: "A5, the composer, wraps the whole document into one page with real design freedom." },
    { at: 0.5, tag: "code", text: "A browser measures it at 1440 and 390 px; only sound pages ship, and a deterministic page waits behind." },
  ] },
  { id: "cosmogon", act: 2, title: "Into Cosmogon", ms: 7500, beats: [
    { at: 0, tag: "result", text: "Same method, one level up: this studio's own look was drawn from the engine's retro references." },
    { at: 0.5, tag: "result", text: "Taste from real references, structure from code, freedom where it's earned. That's how slop stays out." },
  ] },
];

/** The sample query (it matches a real lab run: retro-1976-analog-synth-and-vinyl). */
export const QUERY = "a retro 1976 analog synth & vinyl festival, warm and loud";
export const SPLIT = [
  { k: "What it is", v: "a festival site: nav, hero, about, tickets" },
  { k: "How it feels", v: "retro 1976 · warm · loud → 70s / 80s retro" },
] as const;

export const REFS = [
  { src: "/pipeline/ref-typography.webp", role: "Typography", ref: "TYPOGRAPHY_REF" },
  { src: "/pipeline/ref-background.webp", role: "Background", ref: "BACKGROUND_REF" },
  { src: "/pipeline/ref-layout.webp", role: "Layout", ref: "LAYOUT_REF" },
  { src: "/pipeline/ref-elements.webp", role: "Elements", ref: "ELEMENTS_REF" },
] as const;

/** Sampled from the references, named the way A1 names them (name, hex, where it is used). */
export const PALETTE = [
  { name: "Pine Ink", hex: "#015345", usage: "page ground, deepest wave band" },
  { name: "Marigold", hex: "#F8C43D", usage: "inner ribbon stripe, CTA glow" },
  { name: "Tangerine", hex: "#F28309", usage: "middle ribbon, display shadow" },
  { name: "Signal Vermilion", hex: "#E42603", usage: "pill CTA fill" },
  { name: "Blush Coral", hex: "#E998A1", usage: "outer ribbon stripe" },
  { name: "Sage Mint", hex: "#72AF9C", usage: "muted accent, tags" },
  { name: "Espresso", hex: "#36140D", usage: "body text on linen" },
  { name: "Sunburst Rust", hex: "#BA4A16", usage: "centerpiece rays" },
  { name: "Ray Grey", hex: "#78756C", usage: "alternate rays" },
  { name: "Linen", hex: "#F1D6A1", usage: "panels, text on pine" },
] as const;

/** Twelve of the 39 families (contracts/catalog.json), each with a colour family so clusters read at a glance. */
export const FAMILIES = [
  { name: "70s / 80s retro", colors: ["#F28309", "#F8C43D", "#015345", "#BA4A16"] },
  { name: "Dreamy / ethereal", colors: ["#E8C9E9", "#BFD7F2", "#F6E1D3", "#CBB8E8"] },
  { name: "Neo-brutalist", colors: ["#FFE14D", "#13201B", "#FF5C39", "#FFFDF9"] },
  { name: "Swiss / International", colors: ["#E30613", "#FFFDF9", "#1A1A1A", "#D9D9D9"] },
  { name: "Art deco", colors: ["#0B0B0B", "#C9A64B", "#1F3B33", "#E8D9B0"] },
  { name: "Quiet luxury", colors: ["#D8CFC4", "#A69886", "#F2EDE6", "#6B5E51"] },
  { name: "Cyberpunk / synthwave", colors: ["#FF2E88", "#19F0FF", "#2A0A4A", "#FFB800"] },
  { name: "Organic / earthy", colors: ["#7A8B5C", "#C58B5E", "#E7D8BF", "#4E5B3A"] },
  { name: "Editorial / magazine", colors: ["#111111", "#F2EFE9", "#B8322A", "#8A8A8A"] },
  { name: "Playful / bubbly", colors: ["#FF8FB1", "#7ED3F7", "#FFD84D", "#9B7BFF"] },
  { name: "Cinematic / noir", colors: ["#0E0E0E", "#3A3A3A", "#C9B48A", "#7A1E1E"] },
  { name: "Y2K / Frutiger Aero", colors: ["#7FD6FF", "#C8F2FF", "#3C9BE0", "#E6F7FF"] },
] as const;

export const SEARCHES = ["70s poster", "type specimen", "ui kit", "3d render", "brand identity", "web design", "illustration", "packaging"];

/** What A1 writes: the design document's keys, in order, with a short value each. */
export const DOC_LINES: [string, string][] = [
  ["design_system_name", "\"Analog Sunburst '76\""],
  ["aesthetic_direction", "\"warm 1976 print, grain, ribbons\""],
  ["color_palette_distribution", "[10 named colours]"],
  ["  Marigold #F8C43D", "\"inner ribbon, CTA glow\""],
  ["  Signal Vermilion", "\"pill CTA fill\""],
  ["role_map", "{ bg: Pine Ink, cta: Vermilion }"],
  ["typography", "{ wordmark, display, sub, accent, body }"],
  ["  display", "\"chunky rounded serif, stacked\""],
  ["background_layer", "{ waves, treatment: tinted }"],
  ["centerpiece", "{ sunburst, behind the h1 }"],
  ["midground_decor", "[ rainbow U-bend ribbons ]"],
  ["foreground_overlays", "[ tape, 1976 sticker ]"],
  ["content_sections", "[ nav, hero, about, tickets ]"],
  ["composition_and_overlap_rules", "{ decor under text }"],
];

export const AGENTS = [
  { id: "A2", name: "Layout architect", does: "grid, sizes, where each layer sits", bar: "teal" },
  { id: "A3", name: "Content editor", does: "every word, its level and colours", bar: "gold" },
  { id: "A4", name: "Decor artist", does: "an SVG for each ornament", bar: "vermilion" },
] as const;

export const CHECKS = ["Hex → palette ✓", "Real fonts ✓", "Contrast 4.5:1 ✓", "Unique ids ✓", "SVG sanitised ✓"];
export const GATE = ["1440 px ✓", "390 px ✓", "No text on text ✓", "One h1 ✓", "No overflow ✓"];

export const LAYERS = [
  { n: 0, name: "Backdrop", z: "z-0", what: "pine ground, wave bands" },
  { n: 1, name: "Midground", z: "z-5", what: "U-bend ribbons, sunburst" },
  { n: 2, name: "Content", z: "z-10", what: "nav, h1, about, CTA" },
  { n: 3, name: "Foreground", z: "z-20", what: "tape, sticker" },
  { n: 4, name: "Grain", z: "z-50", what: "print texture" },
] as const;
