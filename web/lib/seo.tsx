// One place for everything search engines and AI crawlers see: domain, author, crawl rules, JSON-LD.
// Links and canonicals stay relative in pages; metadataBase (layout) resolves them against SITE_URL.

export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://cosmogon-labs.vercel.app").replace(/\/$/, "");
/** Only the production deployment is indexable; preview and local builds stay noindex. */
export const IS_PROD = process.env.VERCEL_ENV === "production";

export const SITE_NAME = "Cosmogon Labs";
export const SITE_DESC =
  "Describe a website idea in a sentence. Cosmogon Labs routes its feeling through a structured engine of real design references and composes a full UI design from it. Invite-only research demo.";

export const AUTHOR = {
  name: "Keshav Sharma",
  email: "kesharma21@gmail.com",
  url: "https://www.linkedin.com/in/keshav-sharma-0aa02627b/",
};

/** Indexable pages (the sitemap adds /discover posts on top). */
export const PUBLIC_ROUTES = ["/", "/about", "/evidence", "/discover", "/ai"] as const;
/** Personal areas and the engine API: disallowed in robots.txt and sent with X-Robots-Tag noindex. */
export const PRIVATE_PREFIXES = ["/sites/", "/api/", "/auth/", "/about/assets/"];

export const AI_BOTS = [
  "GPTBot", "OAI-SearchBot", "ChatGPT-User", "ClaudeBot", "Claude-SearchBot", "Claude-User",
  "PerplexityBot", "Perplexity-User", "Google-Extended", "Applebot-Extended", "CCBot", "Bingbot",
];

export const abs = (path: string) => SITE_URL + (path.startsWith("/") ? path : "/" + path);

export const PERSON = {
  "@type": "Person",
  "@id": abs("/ai#person"),
  name: AUTHOR.name,
  email: `mailto:${AUTHOR.email}`,
  url: AUTHOR.url,
  sameAs: [AUTHOR.url],
  jobTitle: "Designer and engineer, Cosmogon Labs",
  knowsAbout: ["web design", "design systems", "computational aesthetics", "information retrieval", "CLIP embeddings", "agentic workflows"],
};

export const ORG = {
  "@type": "Organization",
  "@id": abs("/#org"),
  name: SITE_NAME,
  url: SITE_URL,
  logo: abs("/icon.png"),
  email: `mailto:${AUTHOR.email}`,
  founder: { "@id": PERSON["@id"] },
};

/** Renders schema.org JSON-LD. `<` is escaped so content can never close the script tag. */
export function JsonLd({ data }: { data: object }) {
  const json = JSON.stringify({ "@context": "https://schema.org", ...data }).replace(/</g, "\\u003c");
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: json }} />;
}

/** Per-page metadata with a relative canonical. openGraph/twitter merge shallowly, so the share image is restated. */
export function pageMeta(path: string, title: string, description: string) {
  const images = [{ url: "/opengraph-image", width: 1200, height: 630, alt: `${SITE_NAME}: ${title}` }];
  return {
    title,
    description,
    alternates: { canonical: path },
    openGraph: { type: "website" as const, siteName: SITE_NAME, locale: "en_US", url: path, title, description, images },
    twitter: { card: "summary_large_image" as const, title, description, images: ["/opengraph-image"] },
  };
}

export const NOINDEX = { robots: { index: false, follow: false } };
