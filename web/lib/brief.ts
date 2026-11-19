import { z } from "zod";

/** The parts of DesignBrief v1 (contracts/design_brief.v1.json) the UI reads. Python validates the full schema. */
const Hex = z.string().regex(/^#[0-9a-fA-F]{6}$/);
const Font = z.object({ family: z.string(), category: z.string(), color: z.string(), google_css: z.string().url().optional() });

export const Brief = z.object({
  meta: z.object({
    version: z.literal(1),
    query: z.string(),
    full_query: z.string(),
    vibe_query: z.string(),
    routed_family: z.string(),
    router: z.string(),
    created_at: z.string(),
  }),
  taste: z.object({
    category: z.string(),
    category_name: z.string(),
    niche: z.string().nullable(),
    niche_cues: z.string().nullable().optional(),
    affinity: z.number(),
    clash: z.boolean(),
    avoid: z.array(z.string()),
  }),
  vibe: z.object({ key: z.string(), name: z.string(), cues: z.string(), effect: z.string() }),
  tokens: z.object({
    color: z.record(z.string(), Hex),
    type: z.record(z.string(), z.union([z.string(), z.number()])),
    contrast: z.array(z.object({ pair: z.string(), ratio: z.number(), pass: z.boolean() })),
    palette: z.array(Hex).optional(),
  }),
  fonts: z.object({ heading: Font, body: Font }).nullable(),
  typography: z
    .object({
      overrides: z.array(z.object({ token: z.string(), from: z.unknown(), to: z.unknown(), why: z.string() })).optional(),
    })
    .passthrough()
    .nullable()
    .optional(),
  sections: z.array(z.object({ id: z.string(), layer: z.string(), purpose: z.string() })),
  assets: z.array(
    z.object({ ref_id: z.string(), role: z.string(), fam: z.string(), id: z.string(), cluster: z.string(),
               type: z.string().nullable().optional(), note: z.string().nullable().optional(), path: z.string() }),
  ),
});
export type Brief = z.infer<typeof Brief>;
