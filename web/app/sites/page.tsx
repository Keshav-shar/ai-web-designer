import Link from "next/link";
import { signedMockups } from "@/lib/site";
import { supabaseServer } from "@/lib/supabase/server";

export const metadata = { title: "Sites" };
export const dynamic = "force-dynamic";

type Row = { id: string; title: string | null; created_at: string; mockup_path: string | null; job: { prompt: string; family: string | null } | null };

export default async function SitesPage() {
  const supabase = await supabaseServer();
  // `*` keeps this working before migration 20261121000000_site_mockups.sql adds mockup_path
  const { data } = await supabase
    .from("sites")
    .select("*, job:jobs(prompt, family:brief->meta->>routed_family)")
    .order("created_at", { ascending: false })
    .limit(60)
    .returns<Row[]>();
  const rows = data ?? [];
  const shots = await signedMockups(supabase, rows);
  return (
    <section className="container-x py-14 md:py-20">
      <p className="eyebrow">your sites</p>
      <h1 className="font-heading text-step-7 text-ink">Gallery</h1>
      {!rows.length ? (
        <p className="mt-8 text-muted">Nothing yet. <Link className="underline" href="/">Make the first one.</Link></p>
      ) : (
        <ul className="mt-10 grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((s) => (
            <li key={s.id}>
              <Link href={`/sites/${s.id}`} className="glass block overflow-hidden transition-transform duration-500 hover:-translate-y-1" style={{ padding: 0 }}>
                <div className="aspect-[4/3] overflow-hidden border-b border-line bg-surface/50">
                  {shots.get(s.id) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={shots.get(s.id)} alt={`Mockup of ${s.title ?? "a generated site"}`} className="h-full w-full object-cover object-top" />
                  ) : (
                    <div className="grid h-full place-items-center text-muted">no mockup yet</div>
                  )}
                </div>
                <div className="space-y-1 p-5">
                  <p className="eyebrow" style={{ marginBottom: 0 }}>{s.job?.family ?? "site"}</p>
                  <h2 className="font-heading text-step-3 text-ink">{s.title ?? s.job?.prompt}</h2>
                  <p className="text-[13px] text-muted">{new Date(s.created_at).toLocaleString()}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
