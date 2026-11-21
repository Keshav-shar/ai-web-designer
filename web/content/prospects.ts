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
    "Here is where we're taking it.",
  status: "Current goal",
  items: [
    {
      name: "Motion, with the people who do it best",
      body:
        "We're showing our pages to graphic and motion designers and asking what they would change, frame by frame. " +
        "What we learn becomes a library of motion components the engine can place with the same care it already " +
        "gives to type, colour and layout, so pages move with intent.",
    },
    {
      name: "The right references from the first step",
      body:
        "Search casts a wide net, and some of what it brings back doesn't fit the brief; CLIP clustering sorts most " +
        "of that out today. With AI page parsing in the style of Firecrawl, the engine can read a page and keep only " +
        "what is relevant, right at the source.",
    },
    {
      name: "Your style, as skills and checks",
      body:
        "Each routed design becomes a set of skills, so the agents you connect carry your UI style into their own " +
        "work. A specialised inspector then reviews your product one component at a time, the buttons, the cards, " +
        "the type, and tells you plainly how each one holds up.",
    },
    {
      name: "Local and culturally rooted design",
      body:
        "Niche and regional styles lose the most when AI designs from averages. We want the engine to know as many " +
        "of them as it can: local print traditions, craft and signage, the colours of a particular street or season, " +
        "each kept as its own family, not blended away.",
    },
  ],
  goal: {
    tag: "Our goal",
    lead: "A colourful bouquet.",
    body:
      "Good design should be cheap, quick and measurably effective, not a luxury. When every small business, studio " +
      "and side project can afford real taste, the internet as a whole gets better: more sites that look like " +
      "themselves, and fewer that look like each other.",
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
