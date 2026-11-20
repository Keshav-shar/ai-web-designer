import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { supabaseConfigured } from "@/lib/supabase/config";

// "/" (the studio), "/about" and "/evidence" are public; generating and viewing sites need an invited account.
const PROTECTED = ["/sites", "/api/generate"];
const NOT_CONFIGURED = "This deployment has no Supabase project configured (NEXT_PUBLIC_SUPABASE_URL / _ANON_KEY).";

/** Refreshes the Supabase session cookie on every request and keeps signed-out users out of the app. */
export async function proxy(request: NextRequest) {
  const path = request.nextUrl.pathname;
  const isProtected = PROTECTED.some((p) => path === p || path.startsWith(p + "/"));
  const toLogin = (extra?: Record<string, string>) => {
    const url = request.nextUrl.clone();
    url.pathname = "/login";
    url.search = "";
    url.searchParams.set("next", path);
    Object.entries(extra ?? {}).forEach(([k, v]) => url.searchParams.set(k, v));
    return NextResponse.redirect(url);
  };

  // Misconfigured env must not take the whole site down: public pages still render.
  if (!supabaseConfigured()) {
    if (!isProtected) return NextResponse.next();
    return path.startsWith("/api/") ? NextResponse.json({ error: NOT_CONFIGURED }, { status: 503 }) : toLogin({ error: NOT_CONFIGURED });
  }

  let response = NextResponse.next({ request });
  let user = null;
  try {
    const supabase = createServerClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!, {
      cookies: {
        getAll: () => request.cookies.getAll(),
        setAll: (list) => {
          list.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          list.forEach(({ name, value, options }) => response.cookies.set(name, value, options));
        },
      },
    });
    ({ data: { user } } = await supabase.auth.getUser());
  } catch {
    user = null; // Supabase unreachable: treat as signed out
  }
  if (!user && isProtected) {
    return path.startsWith("/api/") ? NextResponse.json({ error: "sign in first" }, { status: 401 }) : toLogin();
  }
  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|about/assets|.*\\.(?:svg|png|jpg|webp|avif)$).*)"],
};
