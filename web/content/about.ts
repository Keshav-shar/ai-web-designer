// Copy for the About page (ported from contracts/about_copy.json; the FAQ reflects the agent pipeline).
export const ABOUT = {
  hero: {
    eyebrow: "a taste engine for the web",
    title: "Describe a site. Get its taste.",
    sub: "One sentence in. A design recipe drawn from ten thousand real references out, then a page composed from it, section by section.",
  },
  how: {
    title: "Three steps, each one inspectable",
    steps: [
      { n: "01", name: "Split", body: "Your provided sentence is split into two queries: what the site is structurally for, and how it should feel.", bar: "avocado" },
      { n: "02", name: "Taste", body: "The feeling is routed through 39 specialized aesthetic families to Background, Typography, Layout, Elements and Palette from that family's folders, based purely on context similarity with zero AI involvement.", bar: "rust" },
      { n: "03", name: "Serve", body: "Based on evaluated taste, an agentic workflow uses components designed by the vibes, and organizes them into a well-structured high-taste value Landing Page UI", bar: "teal" },
    ],
  },
  showcase: {
    title: "Families are created to capture diversity in designs and prevent AI slop caused by mixing those",
    sub: "Website captures, UI kits, 3D renders, illustration, type specimens and palettes, grouped by CLIP. The studio pulls from the routed family's folders for each section.",
    images: [
      { src: "/about/assets/adc355ed2ce4.webp", caption: "abstract art", tilt: -3 },
      { src: "/about/assets/6ab87d0557a4.webp", caption: "illustration", tilt: 2 },
      { src: "/about/assets/975fb4db6fbf.webp", caption: "3D render", tilt: -1.5 },
      { src: "/about/assets/9944cd9f5cd2.webp", caption: "website capture", tilt: 2.5 },
    ],
  },
  faq: {
    title: "Questions",
    items: [
      ["Where do the images come from?", "A SERP based web-crawling corpus fetches public design references, while specialized clustering algorithms classify them into 39 aesthetic families with ~20 semantic divisions each family. They are shown only to signed-in testers and credited as references."],
      ["Is any of this written by AI?", "The lab that picks palettes, fonts and imagery makes no AI calls, keeping central engine consistent at O(n) updation complexity and high non-agentic feasability. When serving the results, Mistral and Groq models write the design document and compose the page from those picks; every page is then checked by code before it ships."],
      ["What keeps it from looking generic?", "The recipe decides palette, type, scale, alignment and imagery from real references with grounded taste alignments, and guardrails repair anything that fails contrast or the vibe's own cues. You can read more about it in the Evidences page."],
    ],
  },
  cta: { title: "Bring a sentence", sub: "Invite-only while the engine runs on one machine." },
} as const;
