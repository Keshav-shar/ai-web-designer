import { Texture } from "@/components/cosmos";
import { Display, Eyebrow } from "@/components/ui";
import { supabaseConfigured } from "@/lib/supabase/config";
import { LoginForm } from "./login-form";
import { NOINDEX } from "@/lib/seo";

export const metadata = { title: "Sign in", ...NOINDEX };

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
    <section className="container-x grid min-h-[70dvh] place-items-center py-16">
      {/* a print panel beside the form, the form on plain cream */}
      <div className="card grid w-full max-w-[56rem] overflow-hidden md:grid-cols-[1fr_1.15fr]">
        <Texture name="stripes" className="hide-sm border-r-2 border-ink" position="20% center" />
        <div>
          <div aria-hidden="true" className="card-bar bar-vermilion" />
          <div className="p-8 md:p-12">
            <Eyebrow>invite only</Eyebrow>
            <Display as="h1" size={2} className="stacked-sm">Sign in</Display>
            {configured ? (
              <>
                <p className="mt-4">Use the username and password you were given. Accounts are created by invitation only.</p>
                {error && <p role="alert" className="notice mt-5">{error}</p>}
                <LoginForm next={next} />
              </>
            ) : (
              <p role="alert" className="notice mt-5">
                Sign-in isn&rsquo;t available yet: this deployment has no Supabase project configured. Set
                NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY and redeploy.
              </p>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
