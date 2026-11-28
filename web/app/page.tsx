import { Poster } from "@/components/cosmos";
import { PipelineShowcase } from "@/components/pipeline/showcase";
import { Studio, type Engine } from "@/components/studio";
import { Card, Tag } from "@/components/ui";
import { PROSPECTS } from "@/content/prospects";
import { supabaseConfigured } from "@/lib/supabase/config";
import { supabaseServer } from "@/lib/supabase/server";
import { SITE_DESC, pageMeta } from "@/lib/seo";

export const dynamic = "force-dynamic";
const HOME_TITLE = "Cosmogon Labs · Rethinking how AI creates for the visual world";
export const metadata = { ...pageMeta("/", HOME_TITLE, SITE_DESC), title: { absolute: HOME_TITLE } };

async function load() {
  const none = { signedIn: false, job: null, latest: null, engine: null as Engine };
  if (!supabaseConfigured()) return none;
  try {
    const supabase = await supabaseServer();
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return none;
    const [{ data: job }, { data: latest }, { data: engine }] = await Promise.all([
      supabase.from("jobs").select("id, prompt, status").not("status", "in", "(done,failed)")
        .order("created_at", { ascending: false }).limit(1).maybeSingle(),
      supabase.from("sites").select("id, title").order("created_at", { ascending: false }).limit(1).maybeSingle(),
      supabase.from("engine_status").select("state, last_seen, section_mode").order("last_seen", { ascending: false }).limit(1).maybeSingle(),
    ]);
    return { signedIn: true, job, latest, engine: (engine as Engine) ?? null };
  } catch {
    return none;
  }
}

export default async function StudioPage() {
  const { signedIn, job, latest, engine } = await load();
  return (
    <>
      {/* the retro web kit's split hero: lockup left, framed print right, a ruled divider between */}
      <section className="container-x pb-14 pt-12 md:pb-20 md:pt-16">
        <div className="grid items-center gap-12 md:grid-cols-[1.35fr_1fr] md:gap-0">
          <div className="rise md:pr-14">
            <span className="badge">Visual Creation Studio</span>
            <h1 className="mt-9" aria-label="What do you want to bring to life?">
              <span className="inline-caps block text-[clamp(2.1rem,1.3rem+3.4vw,4.1rem)]">
                What do <span className="hl">you</span> want to bring
              </span>
              <span className="display stacked mt-3 block text-[clamp(4.6rem,2.6rem+8vw,9.5rem)] italic leading-[.9]"
                style={{ fontVariationSettings: '"SOFT" 100, "WONK" 1' }}>
                to life?
              </span>
            </h1>
            <p className="lede mt-9">
              Cosmogon Labs is an independent R&amp;D initiative, founded by Keshav Sharma, rethinking how AI understands
              and creates for the visual world. Describe your idea, its purpose and the visual direction you envision;
              the system reads curated visual knowledge and composes a responsive experience around it.
            </p>
          </div>
          <div className="rise-2 hide-sm md:border-l-2 md:border-ink md:pl-14">
            <Poster name="arch" caption="Plate 01 · Sunset arches" artClassName="aspect-square" />
          </div>
        </div>
      </section>
      <section className="container-x relative z-10">
        <Studio signedIn={signedIn} initialJob={job ?? null} latest={latest ?? null} engine={engine} />
      </section>
      {/* the pipeline film: corpus -> taste layer -> agents -> page, under the query box */}
      <section className="container-x relative z-10 pb-20 pt-16 md:pb-28 md:pt-24" aria-labelledby="pipeline-title">
        <p className="eyebrow">Under the surface</p>
        <h2 id="pipeline-title" className="title">Beyond generation. Towards visual understanding.</h2>
        <p className="lede mt-4">
          Generating an interface is only part of the problem; understanding why a composition works is harder.
          Thirteen scenes from the current experimental system: curated visual knowledge built from real references,
          the structured AI orchestration that reads it, and the code that keeps it honest.
        </p>
        <div className="mt-10">
          <PipelineShowcase />
        </div>
      </section>
      {/* research directions: four current directions, then the mission behind them */}
      <section className="section band-sand relative z-10 border-y-2 border-ink" aria-labelledby="prospects-title">
        <div className="container-x">
          <div className="mb-12 max-w-[44rem]">
            <p className="eyebrow">{PROSPECTS.eyebrow}</p>
            <h2 id="prospects-title" className="title">{PROSPECTS.title}</h2>
            <p className="lede mt-4">{PROSPECTS.lede}</p>
          </div>
          <ul className="grid gap-8 md:grid-cols-2">
            {PROSPECTS.items.map((it, i) => (
              <li key={it.name}>
                <Card bar={(["forest", "gold", "vermilion", "teal"] as const)[i % 4]} lift className="h-full">
                  <div className="flex h-full flex-col p-7 pb-8 md:p-8">
                    <h3 className="display mt-4 text-[1.75rem] leading-[1.08]">{it.name}</h3>
                    <p className="mt-4">{it.body}</p>
                  </div>
                </Card>
              </li>
            ))}
          </ul>

          {/* our goal: why the work matters, and the half of the web it is for */}
          <div className="card mt-12 grid overflow-hidden bg-forest text-cream md:mt-16 lg:grid-cols-[1.05fr_1fr]">
            <div className="flex flex-col justify-center p-7 md:p-12">
              <span><span className="tag tag-gold">{PROSPECTS.goal.tag}</span></span>
              <p className="display mt-5 text-[clamp(2.2rem,1.6rem+2.2vw,3.1rem)] italic leading-[1.02] text-gold"
                style={{ fontVariationSettings: '"SOFT" 100, "WONK" 1' }}>
                {PROSPECTS.goal.lead}
              </p>
              <p className="mt-6 max-w-[56ch] text-[1.06rem] leading-[1.7]">{PROSPECTS.goal.body}</p>
              <p className="mt-4 max-w-[56ch] text-[1.06rem] leading-[1.7]">{PROSPECTS.goal.split}</p>
            </div>
            <div className="flex flex-col justify-center gap-6 border-t-2 border-ink p-7 md:p-12 lg:border-l-2 lg:border-t-0">
              {PROSPECTS.goal.lanes.map((l) => (
                <Card key={l.name} bar={l.ours ? "gold" : "teal"} className="text-ink">
                  <div className="p-6">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h3 className="title-sm">{l.name}</h3>
                      {l.ours && <Tag tone="cta">Where we build</Tag>}
                    </div>
                    <p className="mt-3">{l.body}</p>
                  </div>
                </Card>
              ))}
              <p className="text-[0.95rem] leading-[1.6]" style={{ color: "rgba(251,245,239,.86)" }}>{PROSPECTS.goal.closing}</p>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
