import type { MetadataRoute } from "next";
import { POSTS } from "@/content/discover";
import { EVIDENCE_META } from "@/content/evidence.generated";
import { PUBLIC_ROUTES, abs } from "@/lib/seo";

export default function sitemap(): MetadataRoute.Sitemap {
  const latest = POSTS[0]?.updated ?? POSTS[0]?.date;
  const when: Record<string, string | undefined> = {
    "/evidence": EVIDENCE_META.generated_at.slice(0, 10),
    "/ai": EVIDENCE_META.generated_at.slice(0, 10),
    "/discover": latest,
  };
  return [
    ...PUBLIC_ROUTES.map((p) => ({
      url: abs(p),
      lastModified: when[p] ?? latest,
      changeFrequency: (p === "/discover" ? "weekly" : "monthly") as "weekly" | "monthly",
      priority: p === "/" ? 1 : 0.7,
    })),
    ...POSTS.map((p) => ({ url: abs(`/discover/${p.slug}`), lastModified: p.updated ?? p.date, changeFrequency: "monthly" as const, priority: 0.6 })),
  ];
}
