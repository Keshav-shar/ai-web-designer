import { AI } from "@/content/ai";
import { POSTS } from "@/content/discover";
import { AUTHOR, SITE_NAME, abs } from "@/lib/seo";

export const dynamic = "force-static";

// llms.txt (llmstxt.org): a markdown map of the site for language models, built from the /ai facts.
export function GET() {
  const md = [
    `# ${SITE_NAME}`,
    "",
    `> ${AI.summary}`,
    "",
    `Founded by ${AUTHOR.name} (${AUTHOR.email}, ${AUTHOR.url}). ${AI.facts.find(([k]) => k === "Status")?.[1] ?? ""}`,
    "",
    AI.problem,
    "",
    "## Pages",
    ...AI.links.map(([href, label, desc]) => `- [${label}](${abs(href)}): ${desc}`),
    "",
    "## Measured evidence",
    ...AI.evidence.map(([k, v]) => `- ${k}: ${v}`),
    "",
    "## Updates",
    ...POSTS.map((p) => `- [${p.title}](${abs(`/discover/${p.slug}`)}) (${p.date}): ${p.summary}`),
    "",
    "## Optional",
    `- [RSS feed](${abs("/discover/feed.xml")})`,
    `- [Sitemap](${abs("/sitemap.xml")})`,
    "",
  ].join("\n");
  return new Response(md, { headers: { "Content-Type": "text/plain; charset=utf-8" } });
}
