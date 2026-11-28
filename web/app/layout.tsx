import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { fontVars } from "./cosmogon-fonts";
import { Grain } from "@/components/atmosphere";
import { Monogram, Texture } from "@/components/cosmos";
import { SiteNav } from "@/components/site-nav";
import { AUTHOR, IS_PROD, JsonLd, ORG, PERSON, SITE_DESC, SITE_NAME, SITE_URL, abs } from "@/lib/seo";

const SITE_LD = {
  "@graph": [
    { "@type": "WebSite", "@id": abs("/#website"), name: SITE_NAME, url: SITE_URL, description: SITE_DESC, inLanguage: "en", publisher: { "@id": ORG["@id"] }, author: { "@id": PERSON["@id"] } },
    ORG,
    PERSON,
  ],
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: SITE_NAME,
    template: `%s · ${SITE_NAME}`,
  },
  description: SITE_DESC,
  applicationName: SITE_NAME,
  authors: [{ name: AUTHOR.name, url: AUTHOR.url }],
  creator: AUTHOR.name,
  publisher: SITE_NAME,
  keywords: ["visual intelligence", "visual AI research", "AI-driven visual creation", "computer vision", "semantic retrieval", "CLIP embeddings", "design references", "Keshav Sharma"],
  // no site-wide canonical: each public page sets its own, private pages are noindex
  alternates: { types: { "application/rss+xml": [{ url: "/discover/feed.xml", title: `${SITE_NAME} updates` }] } },
  openGraph: { type: "website", siteName: SITE_NAME, locale: "en_US", url: "/", title: SITE_NAME, description: SITE_DESC },
  twitter: { card: "summary_large_image", title: SITE_NAME, description: SITE_DESC },
  // only the production deployment is indexable (previews and local builds stay noindex)
  robots: {
    index: IS_PROD,
    follow: IS_PROD,
    googleBot: { index: IS_PROD, follow: IS_PROD, "max-image-preview": "large", "max-snippet": -1, "max-video-preview": -1 },
  },
  verification: {
    google: "paoiRtAIfn_L0HxOTaJuf6PzR5GhFviRhB1ntt85JTc",
  },
};

export const viewport: Viewport = { themeColor: "#FBF5EF", width: "device-width", initialScale: 1 };

const FOOT = [["/", "Studio"], ["/about", "About"], ["/evidence", "Evidence"], ["/sites", "Your sites"]] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVars}>
      <body>
        <a href="#main" className="btn btn-primary sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70]">
          Skip to content
        </a>
        <SiteNav />
        <main id="main" className="relative z-10">{children}</main>
        <footer className="relative z-10 mt-24 border-t-2 border-ink">
          {/* the wave print (70s-80s-retro / c05): pure texture, no text on it */}
          <Texture name="wave" position="center 40%" className="h-[120px] border-b-2 border-ink sm:h-[180px]" />
          <div className="band-forest">
            <div className="container-x flex flex-wrap items-center justify-between gap-8 py-12">
              <div className="flex items-center gap-3">
                <Monogram className="h-11 w-11" />
                <div>
                  <p className="wordmark text-[1.6rem]" style={{ color: "var(--gold)" }}>Cosmogon Labs</p>
                  <p className="mt-1 text-[0.92rem]" style={{ color: "rgba(251,245,239,.86)" }}>Independent research into visual intelligence and AI-driven creation · Founded by Keshav Sharma</p>
                </div>
              </div>
              <nav aria-label="Footer">
                <ul className="flex flex-wrap gap-x-8 gap-y-3 font-ui text-[0.9rem] font-semibold uppercase tracking-[0.16em]">
                  {FOOT.map(([href, label]) => (
                    <li key={href}><Link className="no-underline hover:text-gold" href={href}>{label}</Link></li>
                  ))}
                </ul>
              </nav>
              <div className="flex w-full flex-wrap justify-between gap-4 border-t pt-6 text-[0.84rem]" style={{ borderColor: "rgba(251,245,239,.2)", color: "rgba(251,245,239,.8)" }}>
                <span>© 2026 Cosmogon Labs. Textures and reference images belong to their authors and are credited as design references.</span>
                <span>For feedback or suggestions, contact <a className="hover:text-gold" href={`mailto:${AUTHOR.email}`}>{AUTHOR.email}</a></span>
              </div>
            </div>
          </div>
        </footer>
        <Grain />
        <JsonLd data={SITE_LD} />
      </body>
    </html>
  );
}
