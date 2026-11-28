import Link from "next/link";
import { POSTS } from "@/content/discover";
import { Display, Eyebrow } from "@/components/ui";
import { fmtDate } from "@/lib/dates";
import { AUTHOR, JsonLd, ORG, abs, pageMeta } from "@/lib/seo";

// Not linked from the UI on purpose: found through the sitemap, RSS and llms.txt.
export const metadata = pageMeta("/discover", "Updates", "Dated updates on Cosmogon Labs, independent research into visual intelligence and AI-driven creation by Keshav Sharma: research notes, evidence and progress.");

export default function DiscoverPage() {
  return (
    <section className="container-x max-w-[52rem] py-14 md:py-20">
      <Eyebrow>updates</Eyebrow>
      <Display as="h1" size={1} className="stacked-sm">Notes from Cosmogon Labs</Display>
      <p className="lede mt-6">Research notes, evidence and progress on visual intelligence and AI-driven creation, by {AUTHOR.name}.</p>
      <ol className="mt-12 space-y-10">
        {POSTS.map((p) => (
          <li key={p.slug} className="border-t-2 border-ink pt-6">
            <p className="meta"><time dateTime={p.date}>{fmtDate(p.date)}</time> · {AUTHOR.name}</p>
            <h2 className="display display-3 mt-2"><Link className="no-underline hover:text-cta" href={`/discover/${p.slug}`}>{p.title}</Link></h2>
            <p className="mt-3">{p.summary}</p>
          </li>
        ))}
      </ol>
      <JsonLd data={{
        "@type": "Blog",
        "@id": abs("/discover#blog"),
        name: "Cosmogon Labs updates",
        url: abs("/discover"),
        publisher: ORG,
        blogPost: POSTS.map((p) => ({
          "@type": "BlogPosting", headline: p.title, url: abs(`/discover/${p.slug}`), datePublished: p.date,
          author: { "@type": "Person", name: AUTHOR.name, url: AUTHOR.url },
        })),
      }} />
    </section>
  );
}
