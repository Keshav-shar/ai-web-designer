import "server-only";
import { z } from "zod";
import catalog from "./catalog.json";
import { SPLIT_PROMPT } from "./split-prompt.generated";

/** Split v1 (contracts/split.v1.json). Same prompt + fallback as worker/split.py. */
export const Split = z.object({
  full_query: z.string().min(1).max(300),
  vibe_query: z.string().min(1).max(300),
  category_hint: z.string().nullable().optional(),
  brand_name: z.string().max(80).nullable().optional(),
  audience: z.string().max(160).nullable().optional(),
  must_sections: z.array(z.string().regex(/^[a-z0-9_]+$/)).max(8).optional(),
  source: z.enum(["qwen", "fallback"]),
});
export type Split = z.infer<typeof Split>;

const CATEGORY_KEYS = new Set(catalog.categories.map((c) => c.key));
const SECTION_IDS = new Set(catalog.section_ids);
const VIBE_WORDS = catalog.vibe_words as Record<string, string[]>;
// "called Dew", "named Moss & Co" -> brand; same regex as worker/split.py
const BRAND = /\b(?:called|named)\s+([A-Z][\w&'.-]*(?:\s+(?:&\s+)?[A-Z][\w&'.-]*){0,3})/;

function systemPrompt(): string {
  return SPLIT_PROMPT.replace("{{FAMILIES}}", catalog.vibes.map((v) => `- ${v.term}: ${v.name}`).join("\n"))
    .replace("{{CATEGORIES}}", catalog.categories.map((c) => `- ${c.key}: ${c.name}`).join("\n"))
    .replace("{{SECTIONS}}", catalog.section_ids.join(", "));
}

export function fallbackSplit(prompt: string): Split {
  const words = prompt.toLowerCase().match(/[a-z0-9]+/g) ?? [];
  const vibe = [...new Set(words.filter((w) => w in VIBE_WORDS))];
  const cat = catalog.categories.find((c) => words.some((w) => c.tokens.includes(w)))?.key ?? null;
  const brand = prompt.match(BRAND)?.[1]?.slice(0, 80) ?? null;
  return {
    full_query: prompt.trim().slice(0, 300),
    vibe_query: (vibe.join(" ") || prompt.trim()).slice(0, 300),
    category_hint: cat,
    brand_name: brand,
    audience: null,
    must_sections: [],
    source: "fallback",
  };
}

function clean(d: Record<string, unknown>, prompt: string): Split {
  const fb = fallbackSplit(prompt);
  const s = (v: unknown, n: number) => (typeof v === "string" && v.trim() ? v.trim().slice(0, n) : null);
  return {
    full_query: s(d.full_query, 300) ?? fb.full_query,
    vibe_query: s(d.vibe_query, 300) ?? fb.vibe_query,
    category_hint: typeof d.category_hint === "string" && CATEGORY_KEYS.has(d.category_hint) ? d.category_hint : null,
    brand_name: s(d.brand_name, 80),
    audience: s(d.audience, 160),
    must_sections: Array.isArray(d.must_sections)
      ? d.must_sections.filter((x): x is string => typeof x === "string" && SECTION_IDS.has(x)).slice(0, 8)
      : [],
    source: "qwen",
  };
}

/** Never throws: any model / network / parse problem falls back to the deterministic split. */
export async function splitPrompt(prompt: string): Promise<Split> {
  const base = process.env.QWEN_BASE?.replace(/\/$/, "");
  const key = process.env.QWEN_API_KEY;
  const model = process.env.QWEN_SPLIT_MODEL;
  if (!base || !key || !model) return fallbackSplit(prompt);
  try {
    const r = await fetch(`${base}/chat/completions`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
      body: JSON.stringify({
        model,
        temperature: 0.1,
        max_tokens: 400,
        response_format: { type: "json_object" },
        messages: [
          { role: "system", content: systemPrompt() },
          { role: "user", content: `Request: ${JSON.stringify(prompt.trim().slice(0, 300))}` },
        ],
      }),
      signal: AbortSignal.timeout(12_000),
    });
    if (!r.ok) return fallbackSplit(prompt);
    const text: string = (await r.json())?.choices?.[0]?.message?.content ?? "";
    const m = text.replace(/<think>[\s\S]*?<\/think>/g, "").match(/\{[\s\S]*\}/);
    return m ? Split.parse(clean(JSON.parse(m[0]), prompt)) : fallbackSplit(prompt);
  } catch {
    return fallbackSplit(prompt);
  }
}
