// Copy for the About page (ported from contracts/about_copy.json; the FAQ reflects the agent pipeline).
// The three step cards are kept close in length (about 40 words each) so the row reads evenly.
export const ABOUT = {
  hero: {
    eyebrow: "a taste engine for the web",
    title: "Describe a site. Get its taste.",
    sub: "One sentence in. A design recipe drawn from ten thousand real references out, then a page composed from it, section by section.",
  },
  how: {
    title: "Three steps, each one inspectable",
    steps: [
      { n: "01", name: "Split", body: "Your sentence is split into two queries: what the site is for, and how it should feel. The first shapes the page's sections and copy, the second its look, so a product name never steers the design off course.", bar: "avocado" },
      { n: "02", name: "Taste", body: "The feeling is matched against 39 specialised aesthetic families. The closest family supplies five references, for background, typography, layout, elements and palette, from its own folders, chosen purely by contextual similarity. No AI model is involved in this step.", bar: "rust" },
      { n: "03", name: "Serve", body: "An agentic workflow turns those references into a landing page. A vision model describes every colour, typeface and shape it sees; text-only agents plan the layout, write the copy and draw the decor; a composer builds the page, and code checks it.", bar: "teal" },
    ],
  },
  showcase: {
    title: "Families keep designs distinct and stop the slop that comes from blending styles",
    sub: "Website captures, UI kits, 3D renders, illustrations, type specimens and palettes, grouped by CLIP. The studio pulls from the routed family's folders for each section.",
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
      ["Where do the images come from?", "A SERP-based web crawler gathers public design references, and specialised clustering sorts them into 39 aesthetic families with about 20 semantic divisions each. They are shown only to signed-in testers and credited as references."],
      ["Is any of this written by AI?", "The lab that picks palettes, fonts and imagery makes no AI calls, so the core engine stays consistent, updates in linear time and runs without agents. When a result is served, open models on OpenRouter and Groq write the design document and compose the page from those picks, and code checks every page before it ships."],
      ["What keeps it from looking generic?", "The recipe decides palette, type, scale, alignment and imagery from real references, grounded in each family's taste, and guardrails repair anything that fails contrast or the vibe's own cues. You can read more on the Evidence page."],
    ],
  },
  cta: { title: "Bring a sentence", sub: "Invite-only while the engine runs on one machine." },
} as const;
