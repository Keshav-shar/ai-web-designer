import Link from "next/link";
import { notFound } from "next/navigation";
import { Sticker } from "@/components/cosmos";
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
    <section className="container-x space-y-8 py-10 md:py-14">
      <Link href="/sites" className="meta no-underline hover:text-sienna">← The gallery</Link>
      <div className="flex flex-wrap items-end justify-between gap-6">
        <div className="max-w-[44rem]">
          <p className="eyebrow">generated site</p>
          <h1 className="display display-2">{label}</h1>
          {job?.prompt && job.prompt !== label && <p className="lede mt-3">&ldquo;{job.prompt}&rdquo;</p>}
        </div>
        <div className="flex flex-wrap gap-3">
          <a className="btn btn-ghost btn-sm" href={`/sites/${id}/preview`} target="_blank" rel="noopener">Open full page</a>
          <a className="btn btn-primary btn-sm" href={`/sites/${id}/download`} download>Download code (.zip)</a>
        </div>
      </div>
      <div className="relative">
        <Sticker top="COSMOGON" script="Studio" big="Mk I" className="drift hide-sm -right-8 -top-10 z-20 w-[112px]" />
        <SiteMockup src={`/sites/${id}/preview`} label={label} />
      </div>
      <div className="text-center"><Link href="/" className="btn btn-primary">Make another</Link></div>
    </section>
  );
}
