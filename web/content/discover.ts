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
    title: "Why Cosmogon Labs keeps design families apart instead of blending styles",
    summary:
      "Averaging many references is what makes AI-generated sites look the same. Cosmogon Labs picks one aesthetic family and draws every choice from it.",
    tags: ["design", "aesthetics", "research"],
    body: [
      "Most generated websites look alike because they average everything they have seen. A palette from one place, a typeface from another and a layout from a third tend to meet in a safe middle.",
      "Cosmogon Labs takes the opposite route. Its references are grouped into 39 specialised aesthetic families, and each request is matched to the single family that fits its feeling best.",
      "## One family, five roles",
      "The routed family supplies the background, typography, layout, elements and palette from its own folders. Because every pick shares one source of taste, the page reads as one design rather than a collage.",
      "## Why it matters",
      "Specialisation keeps results distinct. A wellness retreat and a fintech dashboard land in different families, so they do not converge on the same template.",
    ],
  },
  {
    slug: "what-the-evidence-shows",
    date: "2026-11-24",
    title: "What the evidence shows: routing, contrast and colour tuning in Cosmogon Labs",
    summary:
      "Cosmogon Labs publishes measurements from its own pipeline: how well prompts reach the right aesthetic family and how many colour pairs meet WCAG after tuning.",
    tags: ["evidence", "accessibility", "research"],
    body: [
      "The Evidence page reports measured values, comparisons and corrections taken from the engine's own runs, not illustrations of them.",
      "## Routing",
      "Across 218 test prompts and 39 vibes, the current engine places the expected family first for about two in three prompts and within its top three for close to nine in ten. A prompt that names a vibe directly routes to that vibe every time.",
      "## Contrast",
      "Every composed page is checked against WCAG targets. When a colour needs more contrast, only its lightness is adjusted, so the hue and character of the palette stay intact.",
      "The full charts and tables live on the Evidence page.",
    ],
  },
  {
    slug: "introducing-cosmogon-labs",
    date: "2026-11-21",
    title: "Introducing Cosmogon Labs: a taste engine for the web",
    summary:
      "Cosmogon Labs turns one sentence into a design recipe drawn from thousands of real references, then composes a landing page from it. Built by Keshav Sharma.",
    tags: ["launch", "design", "AI"],
    body: [
      "Cosmogon Labs is a research demo built by Keshav Sharma. You describe a website in a sentence, and the engine answers with a design recipe drawn from real, public design references.",
      "## Three steps",
      "Split: the sentence becomes two queries, what the site is for and how it should feel. Taste: the feeling is matched to one of 39 aesthetic families, which supplies the references. Serve: an agentic workflow composes a landing page from those references, and code checks it before it ships.",
      "## Status",
      "The studio is invite-only while the engine runs on a single machine. Feedback and suggestions are welcome at kesharma21@gmail.com.",
    ],
  },
];

export const postBySlug = (slug: string) => POSTS.find((p) => p.slug === slug);
