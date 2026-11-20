import { HeroCosmos, SunArch } from "@/components/cosmos";
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
      <section className="relative overflow-hidden pb-10 pt-6 text-center md:pt-10">
        <HeroCosmos />
        <div className="container-x relative z-10">
          <SunArch className="rise relative mx-auto -mb-9 block h-[150px] w-[300px] max-w-[80vw] sm:-mb-11 sm:h-[170px] sm:w-[340px]" />
          <h1 className="display display-1 rise relative mx-auto max-w-[14ch]">What should we make?</h1>
          <div className="rise-2 mt-6"><span className="badge">the Studio</span></div>
          <p className="lede rise-3 mx-auto mt-7">
            Name the business and the feeling. Cosmogon Labs routes the feeling to one of 39 aesthetic families,
            reads its references, and composes the page.
          </p>
        </div>
      </section>
      <section className="container-x relative z-10">
        <Studio signedIn={signedIn} initialJob={job ?? null} latest={latest ?? null} engine={engine} />
      </section>
    </>
  );
}
