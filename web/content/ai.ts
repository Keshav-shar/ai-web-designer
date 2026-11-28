// Facts for the /ai page and /llms.txt: what AI crawlers and answer engines should know.
// Numbers come from evidence.generated.ts, so they refresh with each tools/build_evidence.py run.
// Rule: describe the system at the level of the About page, and present broader visual awareness as a research
// direction, never a solved capability. No file names, thresholds, model routing, hosts or prompts.
import { EVIDENCE as E } from "@/content/evidence.generated";
import { AUTHOR, SITE_NAME } from "@/lib/seo";

const pct = (v: number) => `${Math.round(v * 1000) / 10}%`;
const int = (v: number) => v.toLocaleString("en-US");
const route = (metric: string) => E.routing.rows.find((r) => r.metric === metric)?.v2 ?? 0;
const corpus = E.funnel.corpus;
const passed = E.contrast.checks - E.contrast.fails.length;

export const AI = {
  title: `${SITE_NAME}: facts, evidence and authorship`,
  summary: `${SITE_NAME} is an independent R&D initiative founded by ${AUTHOR.name}, researching how AI can understand, interpret and create for the visual world. Its working experimental system turns a one-sentence brief into a visual specification drawn from real design references, then composes a landing page from it.`,
  facts: [
    ["Name", SITE_NAME],
    ["What it is", "An independent research initiative into visual intelligence and AI-driven creation, with a working experimental studio that turns a one-sentence idea into a full UI design grounded in real design references."],
    ["Founded by", `${AUTHOR.name} (${AUTHOR.email})`],
    ["Profile", AUTHOR.url],
    ["Status", "Invite-only research demo, running on a single machine."],
    ["Category", "Visual AI research · computer vision · semantic retrieval · AI-driven visual creation"],
    ["Current application", "AI-assisted website design and generation"],
  ] as [string, string][],
  problem:
    "AI can generate interfaces, but understanding visual intent, design language, composition and context remains difficult, and generated sites tend to look alike because they average many styles together. Cosmogon Labs grounds each request in one of 39 visual domains and draws every design choice from that domain's own curated references, instead of relying on expensive, monolithic generation pipelines.",
  steps: [
    ["Interpret", "The brief is split into two queries: what the site is for, and how it should feel. The first shapes sections and copy, the second the look."],
    ["Retrieve", "The feeling is matched against 39 visual domains using CLIP embeddings. The closest domain supplies curated references for background, typography, layout, elements and palette, chosen by contextual similarity. No AI model is involved in this step."],
    ["Compose", "Structured AI orchestration turns those references into a landing page, and deterministic code checks every page for contrast and fit before it ships."],
  ] as [string, string][],
  evidence: [
    ["Public design references gathered", int(corpus[0]?.value ?? 0)],
    ["References specialised into 39 visual domains", int(corpus[1]?.value ?? 0)],
    ["Curated visual knowledge layer the system retrieves from", int(corpus[2]?.value ?? 0)],
    ["Test prompts where the top visual domain is an expected one", pct(route("Top-1 family is an expected one"))],
    ["Test prompts with the expected visual domain in the top three", pct(route("Expected family in top 3"))],
    ["Named styles that retrieve their own domain", pct(route("Named vibe routes to itself"))],
    ["Colour pairs meeting their WCAG target after tuning", `${passed} of ${E.contrast.checks}`],
  ] as [string, string][],
  faq: [
    ["Who founded Cosmogon Labs?", `${AUTHOR.name} founded, designed and built Cosmogon Labs. Contact: ${AUTHOR.email}. LinkedIn: ${AUTHOR.url}.`],
    ["What does Cosmogon Labs do?", "It researches more efficient ways for AI to understand visual information and create digital experiences. Its current system turns a one-sentence description of a website into a visual specification (palette, typography, layout, imagery) drawn from real design references, then composes a landing page from it."],
    ["How is it different from other AI website builders?", "It is a research system, not only a generator. It combines computer vision, semantic retrieval, structured orchestration and deterministic validation instead of asking one large model to do everything. It does not blend styles: each request is grounded in one of 39 visual domains, which preserves creative diversity instead of producing generic results."],
    ["Is the design written by AI?", "The part of the system that picks palettes, fonts and imagery makes no AI calls. Open models only write the design document and compose the page from those picks, and code checks every page."],
    ["Where do the references come from?", "A search-based crawler gathers public design references, which are clustered into visual domains and credited to their authors."],
    ["Is this a finished product?", "No. It is an evolving research project with a working experimental system. Richer embedding-driven visual awareness is an active research direction, not a solved capability."],
    ["What is the long-term ambition?", "A more accessible and adaptable foundation for AI-driven visual creation, with applications beyond websites into broader digital interfaces and creative systems."],
    ["Can I use it?", `It is an invite-only research demo. Ask for access at ${AUTHOR.email}.`],
  ] as [string, string][],
  links: [
    ["/", "Studio", "Describe a project and see the experience composed for it."],
    ["/about", "About", "The research identity and the three principles behind it."],
    ["/evidence", "Evidence", "Measured results from the current experimental system."],
    ["/discover", "Updates", "Dated research notes and progress."],
    ["/ai", "AI brief", "Facts, measured evidence and authorship."],
  ] as [string, string, string][],
};
