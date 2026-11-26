import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { POSTS, postBySlug } from "@/content/discover";
import { Display, Eyebrow } from "@/components/ui";
import { fmtDate } from "@/lib/dates";
import { AUTHOR, JsonLd, ORG, PERSON, SITE_NAME, abs } from "@/lib/seo";

export const dynamicParams = false;
export const generateStaticParams = () => POSTS.map((p) => ({ slug: p.slug }));

export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const p = postBySlug((await params).slug);
  if (!p) return {};
  const path = `/discover/${p.slug}`;
  return {
    title: p.title,
    description: p.summary,
    keywords: p.tags,
    authors: [{ name: AUTHOR.name, url: AUTHOR.url }],
    alternates: { canonical: path },
    openGraph: {
      type: "article", url: path, title: p.title, description: p.summary, siteName: SITE_NAME,
      publishedTime: p.date, modifiedTime: p.updated ?? p.date, authors: [AUTHOR.url], tags: p.tags,
    },
    twitter: { card: "summary_large_image", title: p.title, description: p.summary },
  };
}

export default async function PostPage({ params }: { params: Promise<{ slug: string }> }) {
  const p = postBySlug((await params).slug);
  if (!p) notFound();
  const url = abs(`/discover/${p.slug}`);
  return (
    <article className="container-x max-w-[46rem] py-14 md:py-20">
      <Link href="/discover" className="meta no-underline hover:text-cta">← All updates</Link>
      <Eyebrow className="mt-8">{p.tags.join(" · ")}</Eyebrow>
      <Display as="h1" size={2} className="stacked-sm">{p.title}</Display>
      <p className="meta mt-5">
        By <a href={AUTHOR.url} rel="author">{AUTHOR.name}</a> · <time dateTime={p.date}>{fmtDate(p.date)}</time>
        {p.updated && <> · updated <time dateTime={p.updated}>{fmtDate(p.updated)}</time></>}
      </p>
      <p className="lede mt-8">{p.summary}</p>
      <div className="mt-8 space-y-5">
        {p.body.map((b, i) => (b.startsWith("## ")
          ? <h2 key={i} className="display display-3 pt-4">{b.slice(3)}</h2>
          : <p key={i}>{b}</p>))}
      </div>
      <p className="mt-12 border-t-2 border-ink pt-6 text-[0.95rem]">
        Questions or feedback: <a href={`mailto:${AUTHOR.email}`}>{AUTHOR.email}</a>. See
        the <Link href="/evidence">Evidence</Link> and <Link href="/about">About</Link> pages.
      </p>
      <JsonLd data={{
        "@type": "NewsArticle",
        headline: p.title,
        description: p.summary,
        image: [`${url}/opengraph-image`],
        datePublished: p.date,
        dateModified: p.updated ?? p.date,
        author: [PERSON],
        publisher: ORG,
        mainEntityOfPage: { "@type": "WebPage", "@id": url },
        keywords: p.tags.join(", "),
        inLanguage: "en",
      }} />
    </article>
  );
}
