import { NextResponse, type NextRequest } from "next/server";
import { previewCsp, renderSite } from "@/lib/site";
import { supabaseServer } from "@/lib/supabase/server";

/** Full-tab view of a generated site. The CSP `sandbox` directive gives it the same isolation as the iframe. */
export async function GET(_req: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[0-9a-f-]{36}$/.test(id)) return new NextResponse("not found", { status: 404 });
  const rendered = await renderSite(await supabaseServer(), id);
  if (!rendered) return new NextResponse("not found", { status: 404 });
  return new NextResponse(rendered.html, {
    headers: {
      "Content-Type": "text/html; charset=utf-8",
      "Content-Security-Policy": previewCsp(true),
      "X-Content-Type-Options": "nosniff",
      "Referrer-Policy": "no-referrer",
      "Cache-Control": "private, no-store",
      "X-Robots-Tag": "noindex",
    },
  });
}
