import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { fontVars } from "./cosmogon-fonts";
import { Grain, Linen } from "@/components/atmosphere";
import { PlanetGlyph } from "@/components/cosmos";
import { SiteNav } from "@/components/site-nav";

export const metadata: Metadata = {
  title: { default: "Cosmogon Labs", template: "%s · Cosmogon Labs" },
  description: "Describe a website in one sentence. Cosmogon Labs routes its feeling through real design references and composes the page. Private research demo.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { themeColor: "#F4F3F0", width: "device-width", initialScale: 1 };

const FOOT = [["/", "Studio"], ["/about", "About"], ["/evidence", "Evidence"], ["/sites", "Your sites"]] as const;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={fontVars}>
      <body>
        <a href="#main" className="btn btn-primary sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[70]">
          Skip to content
        </a>
        <Linen />
        <SiteNav />
        <main id="main" className="relative z-10">{children}</main>
        <footer className="relative z-10 mt-24 bg-espresso text-cream">
          <div aria-hidden="true" className="stripe-band" />
          <div className="container-x flex flex-wrap items-center justify-between gap-8 py-14">
            <div className="flex items-center gap-3">
              <PlanetGlyph className="h-11 w-11" />
              <div>
                <p className="wordmark text-[1.6rem]" style={{ color: "var(--gold-light)" }}>Cosmogon Labs</p>
                <p className="mt-1 text-[0.9rem]" style={{ color: "rgba(251,244,234,.82)" }}>A taste engine for the web · private research demo</p>
              </div>
            </div>
            <nav aria-label="Footer">
              <ul className="flex flex-wrap gap-x-7 gap-y-3 font-ui text-[0.8rem] font-bold uppercase tracking-[0.12em]">
                {FOOT.map(([href, label]) => (
                  <li key={href}><Link className="no-underline hover:text-gold-light" href={href}>{label}</Link></li>
                ))}
              </ul>
            </nav>
            <div className="flex w-full flex-wrap justify-between gap-4 border-t pt-6 text-[0.84rem]" style={{ borderColor: "rgba(251,244,234,.16)", color: "rgba(251,244,234,.74)" }}>
              <span>© Cosmogon Labs. Reference images belong to their authors and are shown to signed-in testers only.</span>
              <span>Composed in one sentence · checked by machine</span>
            </div>
          </div>
        </footer>
        <Grain />
      </body>
    </html>
  );
}
