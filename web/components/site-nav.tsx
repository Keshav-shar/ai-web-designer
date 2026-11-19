import Link from "next/link";
import { supabaseServer } from "@/lib/supabase/server";

export async function SiteNav() {
  let email: string | null = null;
  try {
    const { data } = await (await supabaseServer()).auth.getUser();
    email = data.user?.email ?? null;
  } catch {
    email = null;
  }
  const link = "whitespace-nowrap rounded-full px-2 py-2 hover:text-ink sm:px-3";
  return (
    <header className="sticky top-0 z-40 pt-4">
      <nav aria-label="Main" className="container-x glass flex items-center justify-between gap-2 rounded-full py-2 pl-5 pr-2 sm:gap-4">
        <Link href="/" className="display whitespace-nowrap font-heading text-step-2 text-ink sm:text-step-3">
          serpman <span className="hidden text-accent sm:inline">studio</span>
        </Link>
        <ul className="flex items-center gap-0.5 text-[15px] text-muted sm:gap-2">
          <li><Link className={link} href="/">Studio</Link></li>
          {email && <li><Link className={link} href="/sites">Sites</Link></li>}
          <li><Link className={link} href="/about">About</Link></li>
          <li>
            {email ? (
              <form action="/auth/signout" method="post">
                <button className="btn btn-ghost whitespace-nowrap px-3 py-2 sm:px-4" type="submit">Sign out</button>
              </form>
            ) : (
              <Link className="btn btn-primary whitespace-nowrap px-3 py-2 sm:px-4" href="/login">Sign in</Link>
            )}
          </li>
        </ul>
      </nav>
    </header>
  );
}
