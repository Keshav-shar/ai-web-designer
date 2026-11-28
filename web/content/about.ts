// Copy for the About page: the research identity, the three principles behind it, and the project FAQ.
// The three principle cards are kept close in length (about 40 words each) so the row reads evenly.
export const ABOUT = {
  hero: {
    eyebrow: "independent research & development",
    title: "Building a new foundation for visual AI.",
    sub: "Cosmogon Labs is an independent R&D initiative founded by Keshav Sharma, working where artificial intelligence, computer vision and digital creation meet. It investigates the gap between producing visual output and genuinely understanding the context behind it.",
  },
  how: {
    title: "Three principles behind the research",
    steps: [
      { n: "01", name: "Understand first", body: "Creative intent is more than a text prompt. It carries visual, contextual and structural information. We investigate how computer vision and semantic representations can help AI systems interpret these signals before they make a single creative decision.", bar: "avocado" },
      { n: "02", name: "Lean by design", body: "More parameters and more model calls do not automatically produce better outcomes. We explore lightweight visual knowledge systems and specialised processing that reduce computational overhead while improving contextual relevance, so capable creative systems stay cheap to run.", bar: "rust" },
      { n: "03", name: "Creative control", body: "Generative systems offer flexibility, but reliable results require structure. We combine AI-driven decisions with deterministic constraints, allowing creative variation without sacrificing consistency, responsiveness or technical integrity. Code measures every page before it ships.", bar: "teal" },
    ],
  },
  showcase: {
    title: "Giving machines a richer understanding of visual language",
    sub: "Visual knowledge should be structured, searchable and reusable. Our foundation pairs real-world design references (website captures, UI kits, 3D renders, illustrations, type specimens and palettes) with CLIP embeddings, so the system retrieves examples by context rather than a model's learned defaults. Moving towards more connected visual awareness is an active research direction.",
    images: [
      { src: "/about/assets/adc355ed2ce4.webp", caption: "abstract art", tilt: -3 },
      { src: "/about/assets/6ab87d0557a4.webp", caption: "illustration", tilt: 2 },
      { src: "/about/assets/975fb4db6fbf.webp", caption: "3D render", tilt: -1.5 },
      { src: "/about/assets/9944cd9f5cd2.webp", caption: "website capture", tilt: 2.5 },
    ],
  },
  faq: {
    title: "Questions about the project",
    items: [
      ["What is Cosmogon Labs?", "An independent R&D project exploring more efficient ways for AI systems to understand visual information and create digital experiences. Its current experimental implementation focuses on AI-assisted website design and generation."],
      ["What makes the approach different?", "Rather than depending only on generative models to interpret and produce everything, Cosmogon combines computer vision, semantic retrieval, structured orchestration and deterministic validation. The part that picks palettes, fonts and imagery makes no AI calls; open models write the design document and compose the page from those picks, and code checks every page."],
      ["What technologies underpin the research?", "Python, React, computer vision, CLIP image embeddings, semantic similarity and specialised language and vision models, with programmatic validation for additional control over generated output."],
      ["Where do the references come from?", "A search-based crawler gathers public design references, which are organised into 39 visual domains by clustering. They are shown only to signed-in testers and credited to their authors."],
      ["Is this a finished product?", "No. Cosmogon is an evolving research project with a working experimental system, which serves as a testbed for broader research into visual intelligence and more efficient AI-driven creation. You can read the measurements on the Evidence page."],
      ["What is the long-term ambition?", "A more accessible and adaptable foundation for AI-driven visual creation, with applications reaching beyond websites into broader digital interfaces and creative systems."],
    ],
  },
  cta: { title: "Bring an idea", sub: "Invite-only research demo while the system runs on one machine." },
} as const;
