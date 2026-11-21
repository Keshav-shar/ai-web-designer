/**
 * Copy for the studio's "Future prospects" section (under the pipeline film on /). Plain, calm, specific: what is
 * being worked on next, then the goal behind it. Copy rule (as for the pipeline and the evidence page): frame
 * stages as specialisation and contextual matching, not as loss. The four goal cards are kept close in length
 * (about 48 words each), and so are the two browsing lanes (about 31 words each), so each row reads evenly.
 */

export const PROSPECTS = {
  eyebrow: "Future prospects",
  title: "What we're building next",
  lede:
    "Every mockup on this page is made on free, low-token-limit APIs: a few small model calls, the engine's own " +
    "taste layer, and code that checks the result. Working inside that limit has shaped how the engine thinks. " +
    "This is just the concept, we aim to go much higher.",
  status: "Planned Update",
  items: [
    {
      name: "Interactivity and Motion components",
      body:
        "We present our pages to graphic and motion designers to get reviews on design and structure mocks. " +
        "What we learn builds our library of design and query relevant motion components and static element interactions, with controlled frequency, location and family design relevance so the engine can compare it alongside" +
        "type, colour and layout, so pages move with intent.",
    },
    {
      name: "Relevant data from the first step",
      body:
        "SERP search brings unexpected results for planned queries which don't fit the brief, and CLIP clustering cleans most " +
        "of that out today. Upgrading this with AI page parsing in the style of Firecrawl, the engine will be able to read a page and keep only " +
        "what is relevant, right at the source.",
    },
    {
      name: "Your Agents learn your style",
      body:
        "Each routed design provides a set of skills along with the mock, so the agents you connect with carry your UI style into their own " +
        "work. A specialised inspector then reviews your product one component at a time, the buttons, the cards, " +
        "the type, and tells you plainly how each one holds up.",
    },
    {
      name: "Localized and culturally rooted design",
      body:
        "Niche and regional styles lose the most when AI designs from averages. We teach our engine as many " +
        "styles from them as it can while keeping vibe separate from personalization: local print traditions, craft and signage, the colours of a particular street or season, " +
        "each kept as its own family, not blended away.",
    },
  ],
  goal: {
    tag: "Our goal",
    lead: "A colourful bouquet.",
    body:
      "Good design should be cheap, quick and measurably effective, not a luxury. When every small business, studio " +
      "and side project can afford real taste, the internet as a whole gets better: more sites that look like " +
      "themselves, flavorful and dynamic.",
    split:
      "The web is splitting in two: browsing for agents and browsing for humans. We're building for the second, so " +
      "it stays vibrant even as AI use keeps growing.",
    lanes: [
      {
        name: "Browsing for agents",
        body:
          "Pages read by machines: structured, fast and plain, built for extraction and action. That side of the web " +
          "should be efficient, and we expect AI to do most of the browsing there.",
        ours: false,
      },
      {
        name: "Browsing for humans",
        body:
          "The pages people choose to visit. Even with heavy AI use on both sides of the screen, this web should stay " +
          "vibrant, crafted and varied, never averaged into one safe look.",
        ours: true,
      },
    ],
    closing: "We test every idea on our own engine first, one page at a time, and let what it teaches us shape the next step.",
  },
} as const;
