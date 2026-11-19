/** True when the public Supabase env vars are real (not missing, not the .env.example placeholder). */
export function supabaseConfigured(): boolean {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
  const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";
  return /^https:\/\/[^/]+$/.test(url.replace(/\/$/, "")) && !/YOUR-PROJECT/i.test(url) && key.length > 20;
}
