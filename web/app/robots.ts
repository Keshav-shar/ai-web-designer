import type { MetadataRoute } from "next";
import { AI_BOTS, IS_PROD, PRIVATE_PREFIXES, SITE_URL } from "@/lib/seo";

// Production: public pages open to search and AI crawlers; personal areas and the engine API closed.
// Anything else (Vercel previews, local): closed entirely.
export default function robots(): MetadataRoute.Robots {
  if (!IS_PROD) return { rules: [{ userAgent: "*", disallow: "/" }] };
  const rule = { allow: "/", disallow: PRIVATE_PREFIXES };
  return {
    rules: [{ userAgent: "*", ...rule }, { userAgent: AI_BOTS, ...rule }],
    sitemap: `${SITE_URL}/sitemap.xml`,
    host: SITE_URL,
  };
}
