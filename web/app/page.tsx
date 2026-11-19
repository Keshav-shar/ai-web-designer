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
      supabase.from("engine_status").select("state, last_seen").order("last_seen", { ascending: false }).limit(1).maybeSingle(),
    ]);
    return { signedIn: true, job, latest, engine: (engine as Engine) ?? null };
  } catch {
    return none;
  }
}

export default async function StudioPage() {
  const { signedIn, job, latest, engine } = await load();
  return (
    <section className="container-x py-14 md:py-20">
      <p className="eyebrow">studio</p>
      <h1 className="font-heading text-step-7 text-ink">What should we make?</h1>
      <p className="mt-3 max-w-[60ch] text-muted">
        Name the business and the feeling. The engine routes the feeling to an aesthetic family and composes the site
        from that family&rsquo;s folders.
      </p>
      <Studio signedIn={signedIn} initialJob={job ?? null} latest={latest ?? null} engine={engine} />
    </section>
  );
}
