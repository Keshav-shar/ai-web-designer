import { OrbitRibbon, Sticker, Sunburst, TapePiece } from "@/components/cosmos";
import { Card, Display, Eyebrow } from "@/components/ui";
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
    <section className="relative grid min-h-[70dvh] place-items-center overflow-hidden px-6 py-16">
      <Sunburst className="spin-slow left-1/2 top-1/2 h-[720px] w-[720px] max-w-none" style={{ marginLeft: -360, marginTop: -360 }} opacity={0.12} />
      <OrbitRibbon side="left" className="drift hide-sm -left-6 top-24 w-[200px]" />
      <div className="relative w-full max-w-md">
        <TapePiece style={{ top: -14, left: "50%", marginLeft: -56, transform: "rotate(2deg)" }} />
        <Sticker top="INVITE" script="only" big="✦" className="drift hide-sm -right-12 -top-12 z-20 w-[104px]" />
        <Card bar="rust" className="relative">
          <div className="p-8 md:p-10">
            <Eyebrow>invite only</Eyebrow>
            <Display as="h1" size={2}>Sign in</Display>
            {configured ? (
              <>
                <p className="mt-4 text-espresso">Use the username and password you were given. Accounts are created by invitation only.</p>
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
        </Card>
      </div>
    </section>
  );
}
