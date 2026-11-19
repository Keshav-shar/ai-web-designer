import "server-only";
import type { SupabaseClient } from "@supabase/supabase-js";

const TTL = 60 * 60; // signed URL lifetime (s); the page is private and re-signed on every view

export type SiteRow = { id: string; job_id: string; user_id: string; title: string | null; html_path: string; css_path: string; created_at: string };

/** Origin of the Supabase project, for the generated page's CSP. */
export function supabaseOrigin(): string {
  return new URL(process.env.NEXT_PUBLIC_SUPABASE_URL!).origin;
}

export function previewCsp(sandboxDirective: boolean): string {
  const o = supabaseOrigin();
  return [
    ...(sandboxDirective ? ["sandbox"] : []),
    "default-src 'none'",
    `img-src ${o} data:`,
    `style-src ${o} https://fonts.googleapis.com 'unsafe-inline'`,
    "font-src https://fonts.gstatic.com",
    "base-uri 'none'",
    "form-action 'none'",
    "frame-ancestors 'self'",
  ].join("; ");
}

/**
 * Load a generated site as the signed-in user (RLS + storage policy decide access) and rewrite its relative
 * asset paths to short-lived signed URLs. The page's own meta CSP (written for offline use) is replaced.
 */
export async function renderSite(supabase: SupabaseClient, siteId: string): Promise<{ site: SiteRow; html: string } | null> {
  const { data: site } = await supabase.from("sites").select("*").eq("id", siteId).maybeSingle<SiteRow>();
  if (!site) return null;
  const { data: blob, error } = await supabase.storage.from("sites").download(site.html_path);
  if (error || !blob) return null;
  let html = await blob.text();
  const base = site.html_path.replace(/\/index\.html$/, "");
  const rel = [...new Set([...html.matchAll(/(?:src|href)="((?:assets\/[a-z0-9]{12}\.webp)|styles\.css)"/g)].map((m) => m[1]))];
  if (rel.length) {
    const { data: signed } = await supabase.storage.from("sites").createSignedUrls(rel.map((r) => `${base}/${r}`), TTL);
    const byPath = new Map((signed ?? []).map((s) => [s.path, s.signedUrl]));
    for (const r of rel) {
      const url = byPath.get(`${base}/${r}`);
      if (url) html = html.replaceAll(`"${r}"`, `"${url}"`);
    }
  }
  html = html.replace(/<meta http-equiv="Content-Security-Policy"[^>]*>/i,
    `<meta http-equiv="Content-Security-Policy" content="${previewCsp(false)}">`);
  return { site, html };
}
