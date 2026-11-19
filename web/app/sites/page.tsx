import Link from "next/link";
import { Display, Eyebrow, GlassCard, SwatchRow } from "@/components/ui";
import { supabaseServer } from "@/lib/supabase/server";

export const metadata = { title: "Sites" };
export const dynamic = "force-dynamic";

type Row = { id: string; title: string | null; created_at: string; job: { palette: string[] | null; family: string | null; prompt: string } | null };

export default async function SitesPage() {
  const supabase = await supabaseServer();
  const { data } = await supabase
    .from("sites")
    .select("id, title, created_at, job:jobs(prompt, palette:brief->tokens->palette, family:brief->meta->>routed_family)")
    .order("created_at", { ascending: false })
    .limit(60)
    .returns<Row[]>();
  return (
    <section className="container-x py-16">
      <Eyebrow>your sites</Eyebrow>
      <Display as="h1" step={7}>Gallery</Display>
      {!data?.length ? (
        <p className="mt-8 text-muted">Nothing yet. <Link className="underline" href="/studio">Make the first one.</Link></p>
      ) : (
        <ul className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((s) => (
            <li key={s.id}>
              <Link href={`/sites/${s.id}`} className="block transition-transform duration-500 hover:-translate-y-1">
                <GlassCard className="h-full space-y-4">
                  <p className="eyebrow">{s.job?.family ?? "site"}</p>
                  <h2 className="display font-heading text-step-4 text-ink">{s.title ?? s.job?.prompt}</h2>
                  {s.job?.palette && <SwatchRow colors={s.job.palette} size="sm" />}
                  <p className="text-[13px] text-muted">{new Date(s.created_at).toLocaleString()}</p>
                </GlassCard>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
