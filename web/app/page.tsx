import { Poster } from "@/components/cosmos";
import { PipelineShowcase } from "@/components/pipeline/showcase";
import { Studio, type Engine } from "@/components/studio";
import { supabaseConfigured } from "@/lib/supabase/config";
import { supabaseServer } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

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
            <span className="badge">Welcome to the Studio</span>
            <h1 className="mt-9" aria-label="What should we make?">
              <span className="inline-caps block text-[clamp(2.1rem,1.3rem+3.4vw,4.1rem)]">
                What should <span className="hl">we</span>
              </span>
              <span className="display stacked mt-3 block text-[clamp(4.6rem,2.6rem+8vw,9.5rem)] italic leading-[.9]"
                style={{ fontVariationSettings: '"SOFT" 100, "WONK" 1' }}>
                make?
              </span>
            </h1>
            <p className="lede mt-9">
              Name the business and the feeling. Cosmogon Labs routes the feeling to one of 39 aesthetic families,
              reads its references, and composes the page.
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
        <p className="eyebrow">Inside the engine</p>
        <h2 id="pipeline-title" className="title">How one sentence becomes a page</h2>
        <p className="lede mt-4">
          Thirteen scenes: the taste layer built from real references, the agents that read it, and the code that
          keeps them honest.
        </p>
        <div className="mt-10">
          <PipelineShowcase />
        </div>
      </section>
    </>
  );
}
