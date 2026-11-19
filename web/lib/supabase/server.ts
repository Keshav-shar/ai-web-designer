import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/** Supabase client bound to the signed-in user's cookies. Everything it does runs under RLS as that user. */
export async function supabaseServer() {
  const store = await cookies();
  return createServerClient(env("NEXT_PUBLIC_SUPABASE_URL"), env("NEXT_PUBLIC_SUPABASE_ANON_KEY"), {
    cookies: {
      getAll: () => store.getAll(),
      setAll: (list) => {
        try {
          list.forEach(({ name, value, options }) => store.set(name, value, options));
        } catch {
          // called from a Server Component: the proxy refreshes the session instead
        }
      },
    },
  });
}

export function env(name: string): string {
  const v = process.env[name];
  if (!v) throw new Error(`missing env ${name}`);
  return v;
}
