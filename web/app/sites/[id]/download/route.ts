import JSZip from "jszip";
import { NextResponse, type NextRequest } from "next/server";
import type { SiteRow } from "@/lib/site";
import { supabaseServer } from "@/lib/supabase/server";

/** Zip of the site folder (index.html, styles.css, assets/*) as stored, i.e. with relative paths that work offline. */
export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) return new NextResponse("not found", { status: 404 });
  const supabase = await supabaseServer();
  const { data: site } = await supabase.from("sites").select("*").eq("id", id).maybeSingle<SiteRow>();
  if (!site) return new NextResponse("not found", { status: 404 });
  const base = site.html_path.replace(/\/index\.html$/, "");
  const zip = new JSZip();
  const get = async (rel: string) => {
    const { data } = await supabase.storage.from("sites").download(`${base}/${rel}`);
    if (data) zip.file(rel, await data.arrayBuffer());
  };
  await Promise.all([get("index.html"), get("styles.css")]);
  const { data: list } = await supabase.storage.from("sites").list(`${base}/assets`, { limit: 100 });
  await Promise.all((list ?? []).filter((f) => /^[a-z0-9]{12}(-soft)?\.webp$/.test(f.name)).map((f) => get(`assets/${f.name}`)));
  const body = await zip.generateAsync({ type: "arraybuffer" });
  const name = (site.title ?? "site").toLowerCase().replace(/[^a-z0-9]+/g, "-").slice(0, 40) || "site";
  return new NextResponse(body, {
    headers: {
      "Content-Type": "application/zip",
      "Content-Disposition": `attachment; filename="${name}.zip"`,
      "Cache-Control": "private, no-store",
    },
  });
}
