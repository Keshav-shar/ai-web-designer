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
  return (
    <header className="sticky top-0 z-40 pt-4">
      <nav aria-label="Main" className="container-x glass flex items-center justify-between gap-4 rounded-full px-5 py-2.5">
        <Link href="/" className="display font-heading text-step-3 text-ink">
          serpman <span className="text-accent">studio</span>
        </Link>
        <ul className="flex items-center gap-1 text-muted sm:gap-4">
          {email ? (
            <>
              <li><Link className="rounded-full px-3 py-2 hover:text-ink" href="/studio">Studio</Link></li>
              <li><Link className="rounded-full px-3 py-2 hover:text-ink" href="/sites">Sites</Link></li>
              <li>
                <form action="/auth/signout" method="post">
                  <button className="btn btn-ghost px-4 py-2" type="submit">Sign out</button>
                </form>
              </li>
            </>
          ) : (
            <li><Link className="btn btn-primary px-4 py-2" href="/login">Sign in</Link></li>
          )}
        </ul>
      </nav>
    </header>
  );
}
