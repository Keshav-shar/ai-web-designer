/**
 * Copy for the studio's "Future prospects" section (under the pipeline film on /). Plain, calm, specific: what the
 * engine does today, and what is being worked on next. Copy rule (as for the pipeline and the evidence page): frame
 * stages as specialisation and contextual matching, not as loss.
 */

export const PROSPECTS = {
  eyebrow: "Future prospects",
  title: "What we're building next",
  lede:
    "Every mockup on this page is made on free, low-token-limit APIs: a few small model calls, the engine's own " +
    "taste layer, and code that checks the result. Working inside that limit has shaped how the engine thinks. " +
    "Here is where we're taking it.",
  status: "Currently working on",
  items: [
    {
      name: "Motion, with the people who do it best",
      body:
        "We're showing the pages to graphic and motion designers and asking what they would change. What we learn " +
        "becomes motion components the engine can place with the same care it gives type and colour.",
    },
    {
      name: "The right references from the first step",
      body:
        "Search casts a wide net, and some of what it brings back doesn't fit the brief; CLIP clustering sorts most " +
        "of that out today. With AI page parsing in the style of Firecrawl, the engine can read a page and keep what " +
        "is relevant at the source, from stage one.",
    },
    {
      name: "Your style, as skills",
      body:
        "We're turning each routed design into a full set of skills, so the agents you connect can carry your UI " +
        "style into their own work instead of starting from a blank default.",
    },
    {
      name: "Inspection, one component at a time",
      body:
        "Your style goes through the engine first. Then a specialised inspector looks at each component of your " +
        "product on its own, the buttons, the cards, the type, and tells you how it holds up on design and taste.",
    },
    {
      name: "Local and culturally rooted design",
      body:
        "Niche and regional styles lose the most when AI designs from averages. We want the engine to know as many " +
        "of them as it can: local print traditions, craft, the colours of a particular street or season.",
    },
  ],
  closing: {
    lead: "A colourful bouquet.",
    body:
      "That's the picture we keep coming back to: an internet of sites that each look like themselves, all of them " +
      "made with taste. We test every idea here on our own engine first, one page at a time, and let what it teaches " +
      "us shape the next step.",
  },
} as const;
