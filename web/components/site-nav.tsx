import Link from "next/link";
import { PlanetGlyph } from "@/components/cosmos";
import { usernameOf } from "@/lib/auth/username";
import { supabaseConfigured } from "@/lib/supabase/config";
import { supabaseServer } from "@/lib/supabase/server";

export async function SiteNav() {
  let signedIn = false;
  let username: string | null = null;
  if (supabaseConfigured()) {
    try {
      const { data } = await (await supabaseServer()).auth.getUser();
      signedIn = !!data.user;
      username = usernameOf(data.user);
    } catch {
      signedIn = false;
    }
  }
  const link = "whitespace-nowrap no-underline transition-colors hover:text-sienna";
  return (
    <header className="relative z-30">
      {/* phones: wordmark + account on one row, links on a second; wider: one row */}
      <nav aria-label="Main" className="container-x flex min-h-[88px] flex-wrap items-center justify-between gap-x-3 gap-y-3 py-4 sm:gap-x-8">
        <Link href="/" className="flex items-center gap-2 no-underline sm:gap-2.5" aria-label="Cosmogon Labs, home">
          <PlanetGlyph className="h-9 w-9 shrink-0 sm:h-10 sm:w-10" />
          <span className="wordmark text-[1.2rem] min-[400px]:text-[1.4rem] sm:text-[1.75rem]">Cosmogon Labs</span>
        </Link>
        <ul className="order-last flex w-full items-center justify-between gap-x-6 border-t border-dashed pt-3 font-ui text-[0.75rem] font-bold uppercase tracking-[0.12em] text-charcoal sm:order-none sm:ml-auto sm:w-auto sm:justify-end sm:border-0 sm:pt-0 sm:text-[0.8rem]"
          style={{ borderColor: "var(--rule)" }}>
          <li><Link className={link} href="/">Studio</Link></li>
          {signedIn && <li><Link className={link} href="/sites">Sites</Link></li>}
          <li><Link className={link} href="/about">About</Link></li>
          <li><Link className={link} href="/evidence">Evidence</Link></li>
          {signedIn && username && <li className="hidden normal-case tracking-normal text-muted lg:block" title="signed in">@{username}</li>}
        </ul>
        {signedIn ? (
          <form action="/auth/signout" method="post">
            <button className="btn btn-ghost btn-sm" type="submit">Sign out</button>
          </form>
        ) : (
          <Link className="btn btn-primary btn-sm" href="/login">Sign in</Link>
        )}
      </nav>
    </header>
  );
}
