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
      { n: "01", name: "Split", body: "Your sentence becomes two queries: what the site is for, and how it should feel.", bar: "avocado" },
      { n: "02", name: "Taste", body: "The feeling is routed through 39 aesthetic families to a palette, a type pairing, a scale and imagery from that family's folders.", bar: "rust" },
      { n: "03", name: "Compose", body: "A design document is written from those references and the page is composed from it, then checked: contrast, fonts, overlaps, no scripts, no stray colours.", bar: "teal" },
    ],
  },
  showcase: {
    title: "Every family keeps its own folders",
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
      ["Where do the images come from?", "A research corpus of public design references, clustered into 39 aesthetic families. They are shown only to signed-in testers and credited as references."],
      ["Is any of this written by AI?", "The lab that picks palettes, fonts and imagery makes no AI calls. When the agent pipeline is on, Gemini and Groq models write the design document and compose the page from those picks; every page is then checked by code before it ships."],
      ["What keeps it from looking generic?", "The recipe decides palette, type, scale, alignment and imagery from real references, and guardrails repair anything that fails contrast or the vibe's own cues."],
    ],
  },
  cta: { title: "Bring a sentence", sub: "Invite-only while the engine runs on one machine." },
} as const;
