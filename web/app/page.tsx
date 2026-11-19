import Link from "next/link";
import tokens from "./theme/tokens.json";
import { Chip, Display, Eyebrow, Float, GlassCard, SwatchRow } from "@/components/ui";

const STEPS = [
  { n: "01", t: "Split", d: "Your sentence becomes two queries: what the site is for, and how it should feel." },
  { n: "02", t: "Taste", d: "The vibe is routed through ten thousand real designs to one aesthetic family, its palette, type and imagery." },
  { n: "03", t: "Build", d: "An agent writes each section inside a frame the recipe defines, and a checker rejects anything off-brief." },
];

const FAQ = [
  { q: "Where do the images come from?", a: "A research corpus of public design references, grouped by CLIP into 39 aesthetic families. They are shown only to signed-in testers and credited as references." },
  { q: "Is the output a real website?", a: "A static, script-free page: semantic HTML, compiled Tailwind CSS, Google Fonts. You can download it or keep iterating." },
  { q: "What keeps it from looking generic?", a: "The recipe, not the model, decides the palette, type pairing, scale and sections, and every section is machine-checked against it." },
];

export default function Home() {
  const palette = [tokens.color["--bg"], tokens.color["--surface"], ...tokens.visuals.slice(0, 4), tokens.color["--accent"], tokens.color["--text"]];
  return (
    <>
      {/* hero */}
      <section className="container-x grid items-center gap-14 pb-24 pt-20 md:grid-cols-[1.15fr_.85fr] md:pt-28">
        <div className="fade-up">
          <Eyebrow>a taste engine for the web</Eyebrow>
          <Display as="h1" step={8} className="max-w-[14ch]">
            Describe a site. Get its taste.
          </Display>
          <p className="mt-6 max-w-[52ch] text-step-2 text-muted">
            One sentence in. A design recipe drawn from real references out, then a full page built from it, section by
            section.
          </p>
          <div className="mt-10 flex flex-wrap gap-4">
            <Link href="/studio" className="btn btn-primary">Open the studio</Link>
            <a href="#how" className="btn btn-ghost">How it works</a>
          </div>
        </div>
        <Float className="relative">
          <div aria-hidden="true" className="absolute inset-[8%] -z-10 rounded-full bg-v1 opacity-60 blur-3xl" />
          <GlassCard className="space-y-5">
            <p className="eyebrow">prompt</p>
            <p className="display font-heading text-step-4 text-ink">&ldquo;a tea house in Kyoto that feels wabi-sabi&rdquo;</p>
            <div className="h-px bg-line" />
            <div className="flex flex-wrap gap-2">
              <Chip tone="accent">wabi-sabi-japanese-minimal</Chip>
              <Chip>food</Chip>
              <Chip>Tea ceremony / wabi-sabi</Chip>
            </div>
            <div className="shimmer h-2 rounded-full" />
            <p className="text-muted">routing the vibe &rarr; palette &rarr; type &rarr; sections&hellip;</p>
          </GlassCard>
        </Float>
      </section>

      {/* how it works */}
      <section id="how" className="container-x scroll-mt-28 py-20">
        <Eyebrow>how it works</Eyebrow>
        <Display step={6} className="max-w-[20ch]">Three steps, each one inspectable</Display>
        <ol className="mt-12 grid gap-6 md:grid-cols-3">
          {STEPS.map((s, i) => (
            <li key={s.n}>
              <Float delay={i * 1.3}>
                <GlassCard className="h-full">
                  <p className="font-mono text-[13px] text-muted">{s.n}</p>
                  <h3 className="display mt-3 font-heading text-step-4">{s.t}</h3>
                  <p className="mt-3 text-muted">{s.d}</p>
                </GlassCard>
              </Float>
            </li>
          ))}
        </ol>
      </section>

      {/* showcase: this page's own recipe */}
      <section className="container-x py-20">
        <GlassCard className="grid gap-10 md:grid-cols-2 md:p-12">
          <div>
            <Eyebrow>showcase</Eyebrow>
            <Display step={6}>This page was designed by the lab</Display>
            <p className="mt-5 max-w-[48ch] text-muted">
              Family <strong className="text-ink">{tokens.source.family}</strong>. Its cues are{" "}
              <em>{tokens.vibe.cues.toLowerCase()}</em>. The guardrails changed {tokens.overrides.length} of the
              lab&rsquo;s picks, and every change is logged with its reason.
            </p>
            <div className="mt-8"><SwatchRow colors={palette} size="sm" /></div>
          </div>
          <ul className="space-y-3 text-[15px]">
            {tokens.overrides.slice(0, 6).map((o) => (
              <li key={o.token} className="rounded-2xl border border-line bg-surface/40 px-4 py-3">
                <span className="font-mono text-ink">{o.token}</span>{" "}
                <span className="text-muted">{String(o.from)} &rarr; {String(o.to)}</span>
                <span className="mt-1 block text-muted">{o.why}</span>
              </li>
            ))}
          </ul>
        </GlassCard>
      </section>

      {/* faq */}
      <section className="container-x py-20">
        <Eyebrow>faq</Eyebrow>
        <Display step={6}>Questions</Display>
        <div className="mt-10 divide-y divide-line border-y border-line">
          {FAQ.map((f) => (
            <details key={f.q} className="group py-6">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-6 text-step-3 text-ink">
                {f.q}
                <span aria-hidden="true" className="text-muted transition-transform group-open:rotate-45">+</span>
              </summary>
              <p className="mt-4 max-w-[66ch] text-muted">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* cta */}
      <section className="container-x py-20">
        <div className="relative overflow-hidden rounded-[2.5rem] px-8 py-20 text-center">
          <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[radial-gradient(60%_80%_at_30%_20%,var(--visual-1),transparent_70%),radial-gradient(60%_80%_at_80%_80%,var(--visual-2),transparent_70%)] opacity-80" />
          <Display step={7} className="mx-auto max-w-[16ch]">Bring a sentence</Display>
          <p className="mx-auto mt-5 max-w-[46ch] text-muted">Invite-only while the engine runs on one machine.</p>
          <Link href="/studio" className="btn btn-primary mt-10">Start in the studio</Link>
        </div>
      </section>
    </>
  );
}
