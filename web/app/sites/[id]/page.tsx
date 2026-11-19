import Link from "next/link";
import { notFound } from "next/navigation";
import { Chip, Display, Eyebrow, GlassCard, SwatchRow } from "@/components/ui";
import { Brief } from "@/lib/brief";
import { renderSite } from "@/lib/site";
import { supabaseServer } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function SitePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const supabase = await supabaseServer();
  const rendered = await renderSite(supabase, id);
  if (!rendered) notFound();
  const { data: job } = await supabase.from("jobs").select("prompt, brief").eq("id", rendered.site.job_id).maybeSingle();
  const brief = Brief.safeParse(job?.brief);
  const b = brief.success ? brief.data : null;

  return (
    <section className="container-x py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <Eyebrow>{b?.meta.routed_family ?? "site"}</Eyebrow>
          <Display as="h1" step={6}>{rendered.site.title ?? job?.prompt}</Display>
        </div>
        <div className="flex flex-wrap gap-3">
          <a className="btn btn-ghost" href={`/sites/${id}/preview`} target="_blank" rel="noopener">Open full page</a>
          <a className="btn btn-primary" href={`/sites/${id}/download`}>Download .zip</a>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-[1fr_20rem]">
        {/* sandbox="" : no scripts, no forms, opaque origin; the page is static HTML + CSS anyway */}
        <iframe
          title="Generated site preview"
          sandbox=""
          srcDoc={rendered.html}
          className="h-[78dvh] w-full rounded-[1.75rem] border border-line bg-surface shadow-2xl"
        />
        {b && (
          <aside className="space-y-5">
            <GlassCard className="space-y-4 p-5 md:p-6">
              <p className="eyebrow">recipe</p>
              <SwatchRow colors={Object.values(b.tokens.color).slice(0, 8)} size="sm" />
              <p className="text-[14px] text-ink">{b.fonts?.heading.family} / {b.fonts?.body.family}</p>
              <div className="flex flex-wrap gap-2">
                <Chip>{b.taste.category_name}</Chip>
                {b.taste.niche && <Chip tone="accent">{b.taste.niche}</Chip>}
              </div>
              <p className="text-[13px] text-muted">{b.vibe.cues}</p>
            </GlassCard>
            <GlassCard className="p-5 md:p-6">
              <p className="eyebrow">contrast</p>
              <ul className="mt-2 space-y-1 font-mono text-[12px]">
                {b.tokens.contrast.map((c) => <li key={c.pair} className={c.pass ? "text-muted" : "text-ink"}>{c.pair} {c.ratio} {c.pass ? "ok" : "low"}</li>)}
              </ul>
            </GlassCard>
            {b.typography?.overrides?.length ? (
              <GlassCard className="p-5 md:p-6">
                <p className="eyebrow">guardrail overrides</p>
                <ul className="mt-2 space-y-2 text-[13px] text-muted">
                  {b.typography.overrides.map((o, i) => <li key={i}><span className="font-mono text-ink">{o.token}</span> {o.why}</li>)}
                </ul>
              </GlassCard>
            ) : null}
            <Link href="/studio" className="btn btn-ghost w-full">Make another</Link>
          </aside>
        )}
      </div>
    </section>
  );
}
