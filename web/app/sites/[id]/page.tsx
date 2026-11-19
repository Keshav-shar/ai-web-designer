import Link from "next/link";
import { notFound } from "next/navigation";
import { SiteMockup } from "@/components/site-mockup";
import type { SiteRow } from "@/lib/site";
import { supabaseServer } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export default async function SitePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) notFound();
  const supabase = await supabaseServer();
  const { data: site } = await supabase.from("sites").select("*").eq("id", id).maybeSingle<SiteRow>();
  if (!site) notFound();
  const { data: job } = await supabase.from("jobs").select("prompt").eq("id", site.job_id).maybeSingle();
  const label = site.title ?? job?.prompt ?? "generated site";
  return (
    <section className="container-x space-y-6 py-12">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">generated site</p>
          <h1 className="font-heading text-step-6 text-ink">{label}</h1>
          {job?.prompt && job.prompt !== label && <p className="mt-2 text-muted">&ldquo;{job.prompt}&rdquo;</p>}
        </div>
        <div className="flex flex-wrap gap-3">
          <a className="btn btn-ghost" href={`/sites/${id}/preview`} target="_blank" rel="noopener">Open full page</a>
          <a className="btn btn-primary" href={`/sites/${id}/download`}>Download .zip</a>
        </div>
      </div>
      <SiteMockup src={`/sites/${id}/preview`} label={label} />
      <Link href="/" className="btn btn-ghost">Make another</Link>
    </section>
  );
}
