import Link from "next/link";
import { Texture } from "@/components/cosmos";
import { BARS, Tag } from "@/components/ui";
import { signedMockups } from "@/lib/site";
import { supabaseServer } from "@/lib/supabase/server";
import { NOINDEX } from "@/lib/seo";

export const metadata = { title: "Sites", ...NOINDEX };
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
    <section className="container-x relative py-10 md:py-14">
      <Texture name="rings" className="hide-sm absolute right-0 top-10 h-[150px] w-[260px] border-2 border-ink md:top-14" style={{ boxShadow: "8px 8px 0 var(--ink)" }} position="center 30%" />
      <p className="eyebrow">your sites</p>
      <h1 className="display display-1 stacked-sm">The gallery</h1>
      <p className="lede mt-4">Every experience the studio has composed for you, newest first.</p>
      {!rows.length ? (
        <div className="notice mt-10">Nothing yet. <Link className="font-bold text-cta underline" href="/">Make the first one.</Link></div>
      ) : (
        <ul className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {rows.map((s, i) => (
            <li key={s.id}>
              <Link href={`/sites/${s.id}`} className="card card-lift block h-full overflow-hidden no-underline">
                <div aria-hidden="true" className={`card-bar bar-${BARS[i % BARS.length]}`} />
                <div className="aspect-[4/3] overflow-hidden border-b-2 border-ink bg-sand">
                  {shots.get(s.id) ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={shots.get(s.id)} alt={`Mockup of ${s.title ?? "a generated site"}`} className="h-full w-full object-cover object-top" />
                  ) : (
                    <div className="meta grid h-full place-items-center">no mockup yet</div>
                  )}
                </div>
                <div className="space-y-3 p-6">
                  <Tag tone={(["forest", "gold", "line"] as const)[i % 3]}>{s.job?.family?.replace(/-/g, " ") ?? "site"}</Tag>
                  <h2 className="font-display text-[1.35rem] font-black leading-snug text-forest">{s.title ?? s.job?.prompt}</h2>
                  <p className="meta rule-dashed pt-3">{new Date(s.created_at).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}</p>
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
