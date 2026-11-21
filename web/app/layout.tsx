import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";
import { fontVars } from "./cosmogon-fonts";
import { Grain } from "@/components/atmosphere";
import { Monogram, Texture } from "@/components/cosmos";
import { SiteNav } from "@/components/site-nav";

export const metadata: Metadata = {
  title: { default: "Cosmogon Labs", template: "%s · Cosmogon Labs" },
  description: "Describe a website in one sentence. Cosmogon Labs routes its feeling through real design references and composes the page. Private research demo.",
  robots: { index: false, follow: false },
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
                  <p className="mt-1 text-[0.92rem]" style={{ color: "rgba(251,245,239,.86)" }}>A taste engine for the web · private research demo</p>
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
                <span>© Cosmogon Labs. Textures and reference images belong to their authors and are credited as design references.</span>
                <span>Composed in one sentence · checked by machine</span>
              </div>
            </div>
          </div>
        </footer>
        <Grain />
      </body>
    </html>
  );
}
