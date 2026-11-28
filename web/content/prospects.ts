/**
 * Copy for the studio's "Research directions" section (under the pipeline film on /). Plain, calm, specific: where
 * the research is heading, then the mission behind it. Copy rule (as for the film and the evidence page): present
 * directions as investigations, never as solved capabilities. The four direction cards are kept close in length
 * (about 48 words each), and so are the two browsing lanes (about 31 words each), so each row reads evenly.
 */

export const PROSPECTS = {
  eyebrow: "Research directions",
  title: "Expanding the boundaries of visual intelligence",
  lede:
    "Cosmogon is an evolving research project, and its current system is a foundation for larger possibilities. " +
    "Every mockup on this page is made on free, low-token APIs: a few small model calls, curated visual knowledge " +
    "and code that checks the result. These are the directions in progress now.",
  status: "Planned Update",
  items: [
    {
      name: "Motion with intent",
      body:
        "Our pages are reviewed by graphic and motion designers for structure and design. Those reviews grow a " +
        "library of motion components and static interactions, each tagged by visual domain, frequency and placement, " +
        "so the system weighs motion alongside type, colour and layout, and every movement serves the composition.",
    },
    {
      name: "Relevance at the source",
      body:
        "Search-based gathering surfaces references that don't fit the brief, and CLIP clustering filters most of " +
        "them out today. The next step is AI page parsing in the style of Firecrawl, so the system reads each " +
        "gathered page and keeps only the visual knowledge that is relevant, right at the source.",
    },
    {
      name: "Style-aware agents",
      body:
        "Each routed design will carry a set of skills alongside its mockup, so the agents you connect extend your " +
        "visual language into their own work. A specialised inspector then reviews your product one component at a " +
        "time (buttons, cards, type) and reports plainly how each one holds up.",
    },
    {
      name: "Culturally rooted design",
      body:
        "Niche and regional styles lose the most when AI designs from averages. We are teaching the system as many " +
        "of them as it can hold, while keeping visual direction separate from personalisation: local print " +
        "traditions, craft and signage, the colours of a particular street or season, each preserved as its own " +
        "visual domain.",
    },
  ],
  goal: {
    tag: "Our mission",
    lead: "Creativity should not be gated by resources.",
    body:
      "A compelling digital experience should not depend on expensive tools, large teams or specialised " +
      "infrastructure. The next generation of creative systems should be inexpensive to operate, quick to respond, " +
      "adaptive to context and expressive enough to move beyond repetitive AI-generated aesthetics.",
    split:
      "Our ambition is not simply to automate website creation. It is to explore a better foundation for how " +
      "machines understand and participate in visual creativity.",
    lanes: [
      {
        name: "Browsing for agents",
        body:
          "Pages read by machines: structured, fast and plain, built for extraction and action. Here visual knowledge " +
          "should travel as reusable context, so AI systems stop reconstructing design from scratch.",
        ours: false,
      },
      {
        name: "Browsing for humans",
        body:
          "The pages people choose to visit. As AI shapes more of the web, these should stay distinctive, culturally " +
          "relevant and visually diverse, never averaged into one safe look.",
        ours: true,
      },
    ],
    closing: "A more capable AI. A more expressive web. A more accessible creative future.",
  },
} as const;
