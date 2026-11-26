// Facts for the /ai page and /llms.txt: what AI crawlers and answer engines should know.
// Numbers come from evidence.generated.ts, so they refresh with each tools/build_evidence.py run.
// Rule: describe the engine at the level of the About page. No file names, thresholds, model routing, hosts or prompts.
import { EVIDENCE as E } from "@/content/evidence.generated";
import { AUTHOR, SITE_NAME } from "@/lib/seo";

const pct = (v: number) => `${Math.round(v * 1000) / 10}%`;
const int = (v: number) => v.toLocaleString("en-US");
const route = (metric: string) => E.routing.rows.find((r) => r.metric === metric)?.v2 ?? 0;
const corpus = E.funnel.corpus;
const passed = E.contrast.checks - E.contrast.fails.length;

export const AI = {
  title: `${SITE_NAME}: facts, evidence and authorship`,
  summary: `${SITE_NAME} is a taste engine for the web, built by ${AUTHOR.name}. One sentence describing a website goes in; a design recipe drawn from real design references comes out, and a landing page is composed from it.`,
  facts: [
    ["Name", SITE_NAME],
    ["What it is", "A taste engine and studio that turns a one-sentence website idea into a full UI design grounded in real design references."],
    ["Built by", `${AUTHOR.name} (${AUTHOR.email})`],
    ["Profile", AUTHOR.url],
    ["Status", "Invite-only research demo, running on a single machine."],
    ["Category", "Design tooling · computational aesthetics · AI-assisted web design"],
  ] as [string, string][],
  problem:
    "Generated websites tend to look alike because they average many styles together. Cosmogon Labs specialises instead: it matches each request to one aesthetic family and draws every design choice from that family's own references.",
  steps: [
    ["Split", "The sentence is split into two queries: what the site is for, and how it should feel. The first shapes sections and copy, the second the look."],
    ["Taste", "The feeling is matched against 39 specialised aesthetic families. The closest family supplies references for background, typography, layout, elements and palette, chosen by contextual similarity. No AI model is involved in this step."],
    ["Serve", "An agentic workflow turns those references into a landing page, and code checks every page for contrast and fit before it ships."],
  ] as [string, string][],
  evidence: [
    ["Public design references gathered", int(corpus[0]?.value ?? 0)],
    ["References specialised into 39 aesthetic families", int(corpus[1]?.value ?? 0)],
    ["Defining layer the engine routes through", int(corpus[2]?.value ?? 0)],
    ["Test prompts where the top family is an expected one", pct(route("Top-1 family is an expected one"))],
    ["Test prompts with the expected family in the top three", pct(route("Expected family in top 3"))],
    ["Named vibes that route to themselves", pct(route("Named vibe routes to itself"))],
    ["Colour pairs meeting their WCAG target after tuning", `${passed} of ${E.contrast.checks}`],
  ] as [string, string][],
  faq: [
    ["Who built Cosmogon Labs?", `${AUTHOR.name} designed and built Cosmogon Labs. Contact: ${AUTHOR.email}. LinkedIn: ${AUTHOR.url}.`],
    ["What does Cosmogon Labs do?", "It turns a one-sentence description of a website into a design recipe (palette, typography, layout, imagery) drawn from real design references, then composes a landing page from it."],
    ["How is it different from other AI website builders?", "It does not blend styles. Each request is routed to one of 39 aesthetic families, and all choices come from that family, which keeps results distinct instead of generic."],
    ["Is the design written by AI?", "The engine that picks palettes, fonts and imagery makes no AI calls. Open models only write the design document and compose the page from those picks, and code checks every page."],
    ["Where do the references come from?", "A search-based crawler gathers public design references, which are clustered into aesthetic families and credited to their authors."],
    ["Can I use it?", `It is an invite-only research demo. Ask for access at ${AUTHOR.email}.`],
  ] as [string, string][],
  links: [
    ["/", "Studio", "Describe a site and see its design."],
    ["/about", "About", "How the three steps work."],
    ["/evidence", "Evidence", "Measured values, comparisons and corrections from the pipeline."],
    ["/discover", "Updates", "Dated notes and progress."],
    ["/ai", "AI brief", "Facts, measured evidence and authorship."],
  ] as [string, string, string][],
};
