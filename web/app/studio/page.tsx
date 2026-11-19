import { redirect } from "next/navigation";
import { Display, Eyebrow } from "@/components/ui";
import { supabaseServer } from "@/lib/supabase/server";
import { Studio } from "./studio";

export const metadata = { title: "Studio" };
export const dynamic = "force-dynamic";

export default async function StudioPage() {
  const supabase = await supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect("/login?next=/studio");
  const { data: active } = await supabase
    .from("jobs").select("id, prompt, split, status").not("status", "in", "(done,failed)")
    .order("created_at", { ascending: false }).limit(1).maybeSingle();
  const { data: profile } = await supabase.from("profiles").select("daily_quota").maybeSingle();
  return (
    <section className="container-x py-16">
      <Eyebrow>studio</Eyebrow>
      <Display as="h1" step={7} className="max-w-[18ch]">What should we make?</Display>
      <p className="mt-4 max-w-[56ch] text-muted">
        Name the business and the feeling. &ldquo;A natural wine bar in Lisbon, hand-drawn and loud&rdquo; works better
        than &ldquo;a nice website&rdquo;. {profile ? `${profile.daily_quota} sites per day.` : ""}
      </p>
      <Studio userId={user.id} initialJob={active ?? null} />
    </section>
  );
}
