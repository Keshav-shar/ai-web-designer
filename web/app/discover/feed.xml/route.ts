import { POSTS } from "@/content/discover";
import { AUTHOR, SITE_NAME, abs } from "@/lib/seo";

export const dynamic = "force-static";

const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const rfc822 = (d: string) => new Date(d + "T00:00:00Z").toUTCString();

export function GET() {
  const items = POSTS.map((p) => {
    const link = abs(`/discover/${p.slug}`);
    return [
      "    <item>",
      `      <title>${esc(p.title)}</title>`,
      `      <link>${link}</link>`,
      `      <guid isPermaLink="true">${link}</guid>`,
      `      <pubDate>${rfc822(p.date)}</pubDate>`,
      `      <dc:creator>${esc(AUTHOR.name)}</dc:creator>`,
      ...p.tags.map((t) => `      <category>${esc(t)}</category>`),
      `      <description>${esc(p.summary)}</description>`,
      "    </item>",
    ].join("\n");
  });
  const last = POSTS[0] ? `    <lastBuildDate>${rfc822(POSTS[0].updated ?? POSTS[0].date)}</lastBuildDate>` : "";
  const xml = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom" xmlns:dc="http://purl.org/dc/elements/1.1/">',
    "  <channel>",
    `    <title>${SITE_NAME} updates</title>`,
    `    <link>${abs("/discover")}</link>`,
    `    <atom:link href="${abs("/discover/feed.xml")}" rel="self" type="application/rss+xml" />`,
    `    <description>Research notes, evidence and progress on ${SITE_NAME}: independent research into visual intelligence and AI-driven creation, by ${esc(AUTHOR.name)}.</description>`,
    "    <language>en</language>",
    `    <image><url>${abs("/icon.png")}</url><title>${SITE_NAME} updates</title><link>${abs("/discover")}</link></image>`,
    `    <managingEditor>${AUTHOR.email} (${esc(AUTHOR.name)})</managingEditor>`,
    last,
    ...items,
    "  </channel>",
    "</rss>",
  ].filter(Boolean).join("\n");
  return new Response(xml, { headers: { "Content-Type": "application/rss+xml; charset=utf-8" } });
}
