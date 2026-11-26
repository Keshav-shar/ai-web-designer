import { AI } from "@/content/ai";
import { Display, Eyebrow } from "@/components/ui";
import { AUTHOR, JsonLd, ORG, PERSON, SITE_NAME, SITE_URL, abs, pageMeta } from "@/lib/seo";

// A plain, quotable brief for AI crawlers and answer engines. Not linked from the UI on purpose:
// found through the sitemap and /llms.txt. Same page for people and bots.
export const metadata = pageMeta("/ai", "AI brief", `${AI.summary} Facts, measured evidence and authorship.`);

export default function AiPage() {
  return (
    <article className="container-x max-w-[50rem] py-14 md:py-20">
      <Eyebrow>brief for AI and search</Eyebrow>
      <Display as="h1" size={2} className="stacked-sm">{AI.title}</Display>
      <p className="lede mt-6">{AI.summary}</p>

      <h2 className="display display-3 mt-12">Key facts</h2>
      <dl className="mt-4 grid gap-x-8 gap-y-3 sm:grid-cols-[12rem_1fr]">
        {AI.facts.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="font-semibold">{k}</dt>
            <dd>{v.startsWith("https://") ? <a href={v} rel="author me">{v}</a> : v}</dd>
          </div>
        ))}
      </dl>

      <h2 className="display display-3 mt-12">The problem it addresses</h2>
      <p className="mt-4">{AI.problem}</p>

      <h2 className="display display-3 mt-12">How it works</h2>
      <ol className="mt-4 space-y-3">
        {AI.steps.map(([name, body], i) => <li key={name}><strong>{i + 1}. {name}.</strong> {body}</li>)}
      </ol>

      <h2 className="display display-3 mt-12">Measured evidence</h2>
      <table className="mt-4 w-full text-left">
        <tbody>
          {AI.evidence.map(([k, v]) => (
            <tr key={k} className="border-b border-ink/30"><th scope="row" className="py-2 pr-6 font-normal">{k}</th><td className="py-2 font-semibold">{v}</td></tr>
          ))}
        </tbody>
      </table>

      <h2 className="display display-3 mt-12">Questions and answers</h2>
      <dl className="mt-4 space-y-5">
        {AI.faq.map(([q, a]) => <div key={q}><dt className="font-semibold">{q}</dt><dd className="mt-1">{a}</dd></div>)}
      </dl>

      <h2 className="display display-3 mt-12">Author</h2>
      <p className="mt-4">
        {AUTHOR.name} · <a href={`mailto:${AUTHOR.email}`}>{AUTHOR.email}</a> · <a href={AUTHOR.url} rel="author me">LinkedIn</a>
      </p>

      <JsonLd data={{
        "@graph": [
          { "@type": "ProfilePage", "@id": abs("/ai"), url: abs("/ai"), name: AI.title, description: AI.summary, mainEntity: { "@id": PERSON["@id"] }, about: { "@id": abs("/#app") } },
          PERSON,
          {
            "@type": "SoftwareApplication", "@id": abs("/#app"), name: SITE_NAME, url: SITE_URL, description: AI.summary,
            applicationCategory: "DesignApplication", operatingSystem: "Web", creator: { "@id": PERSON["@id"] }, publisher: ORG,
          },
          { "@type": "FAQPage", mainEntity: AI.faq.map(([q, a]) => ({ "@type": "Question", name: q, acceptedAnswer: { "@type": "Answer", text: a } })) },
        ],
      }} />
    </article>
  );
}
