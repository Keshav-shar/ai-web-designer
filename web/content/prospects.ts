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
    "and code that checks the result. Working inside that limit shapes how the system thinks.",
  status: "Planned Update",
  items: [
    {
      name: "Visual intelligence through embeddings",
      body:
        "Researching richer visual representations that help AI relate composition, typography, colour, structure " +
        "and intent. The aim is stronger reference selection at a fraction of the cost of repeated generative " +
        "interpretation, starting at the source: parsing each gathered page so only relevant visual knowledge is kept.",
    },
    {
      name: "Adaptive generation systems",
      body:
        "Exploring systems that adapt their approach to each project instead of forcing every request through one " +
        "strategy. A modular core leaves room for different levels of complexity, faster iteration and motion: " +
        "interaction components shaped by reviews from graphic and motion designers, placed with intent.",
    },
    {
      name: "Deterministic AI orchestration",
      body:
        "Combining generative flexibility with measurable constraints. Structured decisions, validation gates and " +
        "programmatic correction make AI-generated experiences more predictable, coherent and dependable. Models " +
        "propose; code measures, refines and only lets sound pages through, so creative freedom never costs " +
        "technical integrity.",
    },
    {
      name: "Visual knowledge for connected AI systems",
      body:
        "Investigating how visual understanding can become reusable knowledge, so other AI systems and agents draw on " +
        "design context instead of rebuilding it from scratch. Each design could carry skills your own agents use to " +
        "keep your style, and an inspector that reviews your product component by component.",
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
