import { Display, Eyebrow, GlassCard } from "@/components/ui";
import { supabaseConfigured } from "@/lib/supabase/config";
import { LoginForm } from "./login-form";

export const metadata = { title: "Sign in" };

// Only messages this app itself sends are shown; anything else in ?error= becomes a generic line.
const KNOWN = new Set([
  "This deployment has no Supabase project configured (NEXT_PUBLIC_SUPABASE_URL / _ANON_KEY).",
]);

export default async function LoginPage({ searchParams }: { searchParams: Promise<{ next?: string; error?: string }> }) {
  const sp = await searchParams;
  const next = sp.next?.startsWith("/") && !sp.next.startsWith("//") ? sp.next : "/";
  const configured = supabaseConfigured();
  const error = sp.error ? (KNOWN.has(sp.error) ? sp.error : "Sign-in failed. Please try again.") : null;
  return (
    <section className="container-x grid min-h-[70dvh] place-items-center py-20">
      <GlassCard className="w-full max-w-md md:p-10">
        <Eyebrow>invite only</Eyebrow>
        <Display as="h1" step={6}>Sign in</Display>
        {configured ? (
          <>
            <p className="mt-3 text-muted">Use the email and password you were given. Accounts are created by invitation only.</p>
            {error && <p role="alert" className="mt-4 rounded-2xl border border-line bg-surface px-4 py-3 text-ink">{error}</p>}
            <LoginForm next={next} />
          </>
        ) : (
          <p role="alert" className="mt-4 rounded-2xl border border-line bg-surface px-4 py-3 text-ink">
            Sign-in isn&rsquo;t available yet: this deployment has no Supabase project configured. Set
            NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY and redeploy.
          </p>
        )}
      </GlassCard>
    </section>
  );
}
