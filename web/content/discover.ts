// Dated updates for /discover (search, Google News and Discover). NEWEST FIRST.
// To publish an update: copy one object to the top, change slug/date/title/summary/body, deploy.
// The sitemap, RSS feed, share image and NewsArticle JSON-LD are all built from this list.
// Keep the engine's internals out of posts: describe what it does, never how it is tuned.

export type Post = {
  slug: string; // lowercase-with-hyphens, never change once published
  date: string; // YYYY-MM-DD, first published
  updated?: string; // YYYY-MM-DD, set when you edit a published post
  title: string;
  summary: string; // one or two sentences; used for description, RSS and cards
  tags: string[];
  body: string[]; // paragraphs; a paragraph starting with "## " renders as a subheading
};

export const POSTS: Post[] = [
  {
    slug: "families-not-blends",
    date: "2026-11-26",
    updated: "2026-11-28",
    title: "Preserving creative diversity: why Cosmogon keeps visual domains distinct",
    summary:
      "Averaging many references is what makes AI-generated sites look the same. Cosmogon Labs grounds each request in one visual domain and draws every choice from its curated references.",
    tags: ["design", "visual intelligence", "research"],
    body: [
      "Most generated websites look alike because they average everything they have seen. A palette from one place, a typeface from another and a layout from a third tend to meet in a safe middle.",
      "Cosmogon Labs takes the opposite route. Its curated visual knowledge is organised into 39 visual domains, distinct design languages found by clustering real references, and each request is matched to the single domain that fits its feeling best.",
      "## One domain, five roles",
      "The matched domain supplies the background, typography, layout, elements and palette from its own references. Because every pick shares one design language, the page reads as one coherent design rather than a collage.",
      "## Why it matters",
      "Keeping design languages distinct preserves creative diversity. A wellness retreat and a fintech dashboard land in different domains, so they do not converge on the same template, and the web stays more expressive as AI takes a larger part in creating it.",
    ],
  },
  {
    slug: "what-the-evidence-shows",
    date: "2026-11-24",
    updated: "2026-11-28",
    title: "What the evidence shows: contextual retrieval, contrast and colour in Cosmogon Labs",
    summary:
      "Cosmogon Labs publishes measurements from its own experimental system: how well prompts reach the right visual domain and how many colour pairs meet WCAG after tuning.",
    tags: ["evidence", "accessibility", "research"],
    body: [
      "A different approach to AI creation needs more than an interesting idea; it needs measurable results. The Evidence page reports measured values, comparisons and corrections taken from the system's own runs, not illustrations of them.",
      "## Contextual retrieval",
      "Across 218 test prompts and 39 styles, the current system places an expected visual domain first for about two in three prompts and within its top three for close to nine in ten. A prompt that names a style directly retrieves that style's domain every time.",
      "## Contrast",
      "Every composed page is checked against WCAG targets. When a colour needs more contrast, only its lightness is adjusted, so the hue and character of the palette stay intact: deterministic constraints that preserve visual identity.",
      "The full charts and tables live on the Evidence page.",
    ],
  },
  {
    slug: "introducing-cosmogon-labs",
    date: "2026-11-21",
    updated: "2026-11-28",
    title: "Introducing Cosmogon Labs: independent research into visual intelligence",
    summary:
      "Cosmogon Labs is an independent R&D initiative founded by Keshav Sharma, researching how AI understands and creates for the visual world. Its first demonstration turns one sentence into a complete landing page.",
    tags: ["launch", "visual intelligence", "AI"],
    body: [
      "Cosmogon Labs is an independent R&D initiative founded by Keshav Sharma. It explores how computer vision, semantic retrieval and deterministic systems can work together so AI can interpret visual intent and create for the visual world, without relying on expensive, monolithic generation pipelines.",
      "Its first demonstration is a working experimental studio: you describe a website in a sentence, and the system answers with a visual specification drawn from real, public design references, then composes a landing page from it.",
      "## Three steps",
      "Interpret: the sentence becomes two queries, what the site is for and how it should feel. Retrieve: the feeling is matched to one of 39 visual domains, which supplies curated references. Compose: structured AI orchestration builds a landing page from those references, and code checks it before it ships.",
      "## Status",
      "The studio is an invite-only research demo while the system runs on a single machine. Feedback and suggestions are welcome at kesharma21@gmail.com.",
    ],
  },
];

export const postBySlug = (slug: string) => POSTS.find((p) => p.slug === slug);
