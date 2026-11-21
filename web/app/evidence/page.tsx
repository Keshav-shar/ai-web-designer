import Link from "next/link";
import { EVIDENCE as E, EVIDENCE_META as M } from "@/content/evidence.generated";
import { Texture } from "@/components/cosmos";
import { Display, Eyebrow } from "@/components/ui";
import {
  BarList, ChartCard, DotStrip, Dumbbell, GroupedBars, Legend, SERIES, Stat, StackedBars, Swatch, Table, fmt, fmtPct,
} from "@/components/evidence/charts";

export const metadata = {
  title: "Evidence",
  description: "Measured values, comparisons and corrections from the Cosmogon Labs taste engine's own pipeline.",
};

const pct = (v: number) => fmtPct(v);
const pct1 = (v: number) => fmtPct(v, 1);
const ratio = (v: number) => `${v}`;
const RATIO_AXIS = { min: 1, max: 21, log: true, ticks: [1, 2, 3, 4.5, 7, 12, 21], fmtTick: ratio };
const TEXT_TYPES = ["type specimen", "print / packaging", "logo / branding"];
const HERO_TYPES = ["illustration", "moodboard", "icons", "fashion / product", "3D render", "abstract art"];

/* Display labels for the exported data: each stage is described by what the engine does with it. */
const STAGE: Record<string, string> = {
  "Image and page hits claimed by search": "Public design references gathered by search",
  "Images kept in 39 aesthetic families": "Specialised into 39 aesthetic families",
  "Curated 'cream' layer the engine searches": "Defining 'cream' layer the engine routes through",
  "Images the lab hands forward": "Contextually matched candidates",
  "In the design brief": "Selected for the design brief",
  "Placed on the page": "Placed on the page",
  "Kept as reference (guides layout / colour)": "Guides layout and colour",
};
const stage = (l: string) => STAGE[l] ?? l;
const STATUS = [
  { key: "on page", label: "Placed on the page", color: SERIES.s1 },
  { key: "reference", label: "Guides layout and colour", color: SERIES.s4 },
  { key: "unused", label: "In the brief, held as an alternate", color: SERIES.s2 },
  { key: "dropped", label: "Matched, beyond the focused brief", color: SERIES.base },
] as const;
const REASON: Record<string, string> = {
  "Folder cap (18 per brief)": "Brief stays focused on the 18 strongest folder matches",
  "Every matching slot filled": "Alternate for a slot already filled",
  "No section takes this image type": "Kept for a section type this page doesn't use",
  "Duplicate of an earlier pick": "Merged with an identical pick",
  "Only one hero visual per page": "Alternate hero (one hero per page)",
  "Baked-in text": "Lettered art kept out of picture slots",
};

export default function EvidencePage() {
  const clip = E.views.rows.find((r) => r.label === "CLIP image")!;
  const bestHand = E.views.rows.filter((r) => !r.clip)[0];
  const r = E.routing;
  const top3 = r.rows[1];
  const passed = E.contrast.checks - E.contrast.fails.length;
  const byType = new Map(E.text.rows.map((x) => [x.type, x]));
  const textRows = (types: string[]) => types.map((t) => byType.get(t)).filter((x) => x != null);
  const clears = (t: string) => pct(1 - (byType.get(t)?.clip ?? 0));
  const fixes = E.corrections;
  const reached = fixes.filter((f) => f.reached).length;
  const totalTaken = E.placement.rows.reduce((a, x) => a + x["on page"] + x.reference + x.unused + x.dropped, 0);
  const gateTotal = E.gate.kinds.reduce((a, k) => a + k.n, 0);
  // one row per displayed reason (the export splits some reasons by status)
  const reasons = [...E.placement.reasons.reduce((m, x) => {
    const label = REASON[x.reason] ?? x.reason;
    const row = m.get(label) ?? { label, n: 0, held: false };
    row.n += x.n;
    row.held ||= x.status !== "dropped";
    return m.set(label, row);
  }, new Map<string, { label: string; n: number; held: boolean }>()).values()].sort((a, b) => b.n - a.n);

  return (
    <div className="container-x relative pb-10 pt-12 md:pt-16">
      <header className="grid items-end gap-10 md:grid-cols-[1.7fr_1fr]">
        <div>
          <Eyebrow>Evidence</Eyebrow>
          <Display as="h1" size={1} className="stacked-sm">What the engine measures, compares and corrects</Display>
          <p className="lede mt-6">
            Every number on this page comes from the pipeline&rsquo;s own data and code paths. There are no human ratings,
            and the lab that picks images, palettes and fonts makes no AI calls. Each chart says what it shows and how
            many runs it rests on.
          </p>
        </div>
        <Texture name="tiles" className="hide-sm h-[260px] border-2 border-ink" style={{ boxShadow: "8px 8px 0 var(--ink)" }} />
      </header>

      <div className="card mt-14 grid grid-cols-2 gap-8 p-6 sm:p-8 lg:grid-cols-4">
        <Stat label="Reference images, specialised" value={fmt(E.funnel.corpus[1].value)} sub={`in ${r.vibes} aesthetic families`} />
        <Stat label="CLIP vs best hand-built feature" value={`${pct(clip.hit1)} vs ${pct(bestHand.hit1)}`} sub="nearest-neighbour hit rate" />
        <Stat label="Expected family in router's top 3" value={pct(top3.v2)} sub={`over ${r.queries} category queries`} />
        <Stat label="Colour pairs meeting WCAG" value={`${passed} / ${E.contrast.checks}`} sub={`after tuning, ${E.contrast.runs} pages`} />
      </div>

      <nav aria-label="Charts" className="mt-10 flex flex-wrap gap-2 text-[14px]">
        {[["curation", "1 Curation"], ["representation", "2 Representation"], ["routing", "3 Routing"], ["text", "4 Text filter"],
          ["contrast", "5 Contrast"], ["corrections", "6 Colour tuning"], ["placement", "7 Image matching"], ["gate", "8 Agent gate"]].map(([id, l]) => (
          <a key={id} href={`#${id}`} className="btn btn-ghost btn-sm">{l}</a>
        ))}
      </nav>

      <div className="mt-12 grid gap-10">
        {/* 1 ------------------------------------------------------------ curation */}
        <ChartCard id="curation" kicker="1 · Corpus → page" title="Every family is distilled to the references that define it"
          shows={<>Search gathered {fmt(E.funnel.corpus[0].value)} public design references. CLIP specialises them into {r.vibes} aesthetic families,
            and the engine routes through the {fmt(E.funnel.corpus[2].value)} that define each cluster best: the <em>cream</em>, images typical of their
            cluster without being its most generic (fit between +{E.funnel.cream_rule.band_sigma[0]}σ and +{E.funnel.cream_rule.band_sigma[1]}σ).
            For a single page the lab surfaces about {Math.round(E.funnel.per_page[0].value)} contextually matched candidates. About {Math.round(E.funnel.per_page[1].value)} shape
            the design brief and about {Math.round(E.funnel.per_page[2].value)} are placed, each in the slot it suits.</>}
          n={`Corpus counts from the scrape database and the family summaries. Per-page values are means of ${E.funnel.runs} fixed prompts run through the lab and compose bench with baseline controls.`}
          table={<Table head={["Stage", "Count"]} rows={[...E.funnel.corpus.map((x) => [stage(x.label), x.value]), ...E.funnel.per_page.map((x) => [`Per page: ${stage(x.label)}`, x.value])]} />}>
          <h3 className="mb-3 font-ui text-[15px] font-semibold uppercase tracking-[.1em] text-ink">Corpus</h3>
          <BarList max={150000} ticks={[0, 50000, 100000, 150000]} fmtTick={(v) => (v ? `${v / 1000}K` : "0")}
            rows={E.funnel.corpus.map((x) => ({ label: stage(x.label), value: x.value, color: SERIES.s1 }))} />
          <h3 className="mb-3 mt-10 font-ui text-[15px] font-semibold uppercase tracking-[.1em] text-ink">One page (mean of {E.funnel.runs})</h3>
          <BarList max={60} ticks={[0, 20, 40, 60]}
            rows={E.funnel.per_page.map((x, i) => ({ label: stage(x.label), value: x.value, color: i === 3 ? SERIES.s4 : SERIES.s1 }))} />
        </ChartCard>

        {/* 2 ------------------------------------------------------------ representation */}
        <ChartCard id="representation" kicker="2 · Representation" title="CLIP embeddings capture design taste better than hand-built features"
          shows={<>For every image we checked whether its nearest neighbour came from the same kind of source: a palette sheet, a font specimen,
            a UI kit, an effect or a site. CLIP&rsquo;s image embedding finds one {pct(clip.hit1)} of the time, against {pct(bestHand.hit1)} for the best
            hand-built colour, edge, layout and text-box features. That is why routing, cream and the text filter all run on CLIP.</>}
          n={`One family fingerprinted so far (${E.views.family}, ${E.views.items} images, ${E.views.labels.length} source labels). Chance is ${pct(E.views.chance)}.`}
          table={<Table head={["View", "hit@1", "Cluster purity"]} rows={E.views.rows.map((x) => [x.label, pct1(x.hit1), pct1(x.purity)])} />}>
          <Legend items={[{ label: "CLIP embedding", color: SERIES.s1 }, { label: "Hand-built features", color: SERIES.base }]} />
          <BarList max={1} ticks={[0, 0.25, 0.5, 0.75, 1]} fmtTick={pct} fmtValue={pct} refs={[{ at: E.views.chance, label: "chance" }]}
            rows={E.views.rows.map((x) => ({ label: x.label, value: x.hit1, color: x.clip ? SERIES.s1 : SERIES.base }))} />
        </ChartCard>

        {/* 3 ------------------------------------------------------------ routing */}
        <ChartCard id="routing" kicker="3 · Routing" title="Router v2 sends more queries to the family a designer would expect"
          shows={<>Each category query in the taste catalog lists the vibes that suit it, and the router picks a family. v2 widens each family&rsquo;s
            pool to every website-type image and weights the family-name prior a little more. It leads v1 on all three measures and
            reaches {r.families_used.v2} of {r.vibes} families (v1: {r.families_used.v1}).</>}
          n={`${r.queries} category queries plus ${r.vibes} "<vibe> website design" queries, re-run for this page. Both routers run their default settings. No model is involved.`}
          table={<Table head={["Measure", "v1", "v2"]} rows={r.rows.map((x) => [x.metric, pct1(x.v1), pct1(x.v2)])} />}>
          <Legend items={[{ label: "Router v1", color: SERIES.base }, { label: "Router v2", color: SERIES.s1 }]} />
          <GroupedBars max={1} ticks={[0, 0.25, 0.5, 0.75, 1]} fmtTick={pct} fmtValue={pct1}
            series={[{ label: "v1", color: SERIES.base }, { label: "v2", color: SERIES.s1 }]}
            rows={r.rows.map((x) => ({ label: x.metric, values: [x.v1, x.v2] }))} />
        </ChartCard>

        {/* 4 ------------------------------------------------------------ text filter */}
        <ChartCard id="text" kicker="4 · Text-free imagery" title={`CLIP clears ${clears("3D render")} of 3D renders for hero use and routes lettering to type`}
          shows={<>Hero and supporting visuals should carry no baked-in text, so every image is read for lettering first. The CLIP check (text prompts minus
            no-text prompts, threshold {E.text.threshold}) recognises the lettering in type specimens and packaging, and clears {clears("3D render")} of 3D renders,
            {" "}{clears("abstract art")} of abstract art and {clears("fashion / product")} of product imagery for picture slots. A pixel text detector (more
            than {E.text.pixel_rule.max_lines} lines, or one block taller than {pct(E.text.pixel_rule.max_height)} of the image) would clear
            only {pct(1 - (byType.get("3D render")?.pixel ?? 0))} of 3D renders, which is why the engine reads text with CLIP.</>}
          n={`All ${fmt(E.text.images)} cream images, grouped by their cluster type. Both methods run on the same images.`}
          table={<Table head={["Image type", "Images", "Read as text by CLIP", "Read as text by pixels", "CLIP median"]}
            rows={E.text.rows.map((x) => [x.type, x.n, pct(x.clip), pct(x.pixel), x.median.toFixed(3)])} />}>
          <Legend items={[{ label: "Read as text by CLIP", color: SERIES.s1 }, { label: "Read as text by a pixel detector", color: SERIES.s2 }]} />
          <h3 className="mb-3 font-ui text-[15px] font-semibold uppercase tracking-[.1em] text-ink">Lettering types, routed to type and print</h3>
          <GroupedBars max={1} fmtValue={pct} series={[{ label: "CLIP", color: SERIES.s1 }, { label: "Pixel", color: SERIES.s2 }]}
            rows={textRows(TEXT_TYPES).map((x) => ({ label: x.type, values: [x.clip, x.pixel] }))} />
          <h3 className="mb-3 mt-10 font-ui text-[15px] font-semibold uppercase tracking-[.1em] text-ink">Picture types, cleared for hero slots</h3>
          <GroupedBars max={1} ticks={[0, 0.25, 0.5, 0.75, 1]} fmtTick={pct} fmtValue={pct}
            series={[{ label: "CLIP", color: SERIES.s1 }, { label: "Pixel", color: SERIES.s2 }]}
            rows={textRows(HERO_TYPES).map((x) => ({ label: x.type, values: [x.clip, x.pixel] }))} />
        </ChartCard>

        {/* 5 ------------------------------------------------------------ contrast */}
        <ChartCard id="contrast" kicker="5 · Colour contrast" title={`${passed} of ${E.contrast.checks} colour pairs meet their WCAG target`}
          shows={<>Each page&rsquo;s palette comes from its family&rsquo;s images, and the guardrail holds it to WCAG: text at 4.5:1, main text at 7:1 on the
            background where it can, and button fills at 3:1 on the page. On the one mid-toned surface in the set (dreamy ethereal) it lifts text
            all the way to white, the strongest contrast that surface allows ({E.contrast.fails[0]?.ratio}:1).</>}
          n={`${E.contrast.runs} pages, 6 pairs each, log scale. One dot per page. Hover a dot for its prompt.`}
          table={<Table head={["Pair", "Target", "Lowest", "Per page"]} rows={E.contrast.rows.map((x) => [x.pair, `${x.target}:1`, x.min, x.points.map((p) => p.ratio).join(" · ")])} />}>
          <Legend items={[{ label: "Meets its target", color: SERIES.s1, shape: "dot" }, { label: "At the surface's white limit", color: SERIES.s4, shape: "dot" }]} />
          <DotStrip {...RATIO_AXIS} color={SERIES.s1}
            refs={[{ at: 3, label: "3:1" }, { at: 4.5, label: "4.5:1" }, { at: 7, label: "7:1" }]}
            rows={E.contrast.rows.map((x) => ({
              label: <>{x.pair} <span className="text-muted">· needs {x.target}:1</span></>,
              points: x.points.map((p) => ({ v: p.ratio, title: `${p.query}: ${p.ratio}:1`, color: p.pass ? undefined : SERIES.s4 })),
            }))} />
        </ChartCard>

        {/* 6 ------------------------------------------------------------ corrections */}
        <ChartCard id="corrections" kicker="6 · Colour tuning" title={`The guardrail tunes ${fixes.length} palette colours for legibility and keeps each family's hue`}
          shows={<>When a palette colour needs more contrast against its pair, the guardrail moves only its OKLab lightness and keeps hue and chroma.
            It makes the smallest change that reaches the target, so the page keeps the family&rsquo;s colour: {reached} of {fixes.length} land exactly on
            target, and the rest go as far as their surface allows. Each row shows the lab&rsquo;s colour and the shipped colour; the tick marks the target.</>}
          n={`Every lightness adjustment across the ${E.contrast.runs} pages. Colours that already met their target needed none and are not shown. Log scale.`}
          table={<Table head={["Prompt", "Token", "On", "Lab → shipped", "Before", "After", "Target"]}
            rows={fixes.map((f) => [f.query, f.token, f.on, `${f.from} → ${f.to}`, f.before, f.after, f.target])} />}>
          <Legend items={[{ label: "Lab colour", color: SERIES.base, shape: "dot" }, { label: "Shipped colour", color: SERIES.s1, shape: "dot" },
            { label: "Shipped, at the surface's white limit", color: SERIES.s4, shape: "dot" }]} />
          <Dumbbell {...RATIO_AXIS} before={SERIES.base} after={SERIES.s1}
            rows={fixes.map((f) => ({
              a: f.before, b: f.after, target: f.target, afterColor: f.reached ? undefined : SERIES.s4,
              title: `${f.query}: ${f.token} ${f.from} → ${f.to} on ${f.on} (${f.against})`,
              label: (
                <span className="inline-flex flex-wrap items-center gap-x-1.5 sm:justify-end">
                  <Swatch hex={f.from} /><span aria-hidden className="text-muted">→</span><Swatch hex={f.to} />
                  <span>{f.token.slice(2)} on {f.on.slice(2)}</span>
                  <span className="w-full text-[12px] text-muted sm:text-right">{f.query}</span>
                </span>
              ),
            }))} />
        </ChartCard>

        {/* 7 ------------------------------------------------------------ placement */}
        <ChartCard id="placement" kicker="7 · Image matching" title="The engine presents only contextually matched images"
          shows={<>Every candidate comes from the prompt&rsquo;s own family, so everything traced here already fits the brief&rsquo;s context. The compose bench
            follows each one from the lab run to the page. The brief stays focused on the 18 strongest folder matches, each image goes to the slot
            type it suits (one hero visual, sections that take its kind of image), and close alternates are held for slots already filled.</>}
          n={`${E.placement.rows.length} fixed prompts, ${totalTaken} traced images. Routed families are shown under each prompt.`}
          table={<Table head={["Prompt", "Family", ...STATUS.map((s) => s.label)]} rows={E.placement.rows.map((x) => [x.query, x.family, ...STATUS.map((s) => x[s.key])])} />}>
          <Legend items={STATUS.map((s) => ({ label: s.label, color: s.color }))} />
          <StackedBars series={STATUS.map((s) => ({ label: s.label, color: s.color }))}
            rows={E.placement.rows.map((x) => ({
              label: <span>{x.query}<span className="block text-[12px] text-muted">{x.family}</span></span>,
              values: STATUS.map((s) => x[s.key]),
            }))} />
          <h3 className="mb-3 mt-10 font-ui text-[15px] font-semibold uppercase tracking-[.1em] text-ink">How each match was used, all runs</h3>
          <BarList max={200} ticks={[0, 50, 100, 150, 200]}
            rows={reasons.map((x) => ({ label: x.label, value: x.n, color: x.held ? SERIES.s2 : SERIES.base }))} />
        </ChartCard>

        {/* 8 ------------------------------------------------------------ agent gate */}
        <ChartCard id="gate" kicker="8 · Agent gate" title="Code gates refine the models’ layout before a page ships"
          shows={<>In the 5-agent landing pipeline, models propose the layout, groups, motifs and composition, and code measures and refines them.
            On the live model run, the gates refined {gateTotal} decisions in a single pass before the page shipped, with no regeneration.</>}
          n={`${E.gate.runs} live model run${E.gate.runs === 1 ? "" : "s"} so far. Free-tier model quotas allow about 10 sites a day, and more runs will be added as they are made. Runs with the models off are excluded.`}
          table={<Table head={["Refinement", "Count"]} rows={E.gate.kinds.map((k) => [k.kind, k.n])} />}>
          <BarList max={Math.max(6, ...E.gate.kinds.map((k) => k.n))}
            rows={E.gate.kinds.map((k) => ({ label: k.kind, value: k.n, color: SERIES.s1 }))} />
        </ChartCard>
      </div>

      <p className="mt-12 max-w-[64ch] text-[13px] text-muted">
        Generated {M.generated_at.slice(0, 10)} from {M.bench_runs} bench runs and {M.landing_runs} landing run{M.landing_runs === 1 ? "" : "s"}. The lab export
        (evidence_export.py) is read-only. It never advances the lab&rsquo;s shared cursor and never calls a model.
        Prompts: {E.prompts.join(" · ")}. See also <Link className="underline hover:text-ink" href="/about">how the engine works</Link>.
      </p>
    </div>
  );
}
