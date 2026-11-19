import type { Metadata, Viewport } from "next";
import "./globals.css";
import { bodyFont, headingFont } from "./fonts";
import tokens from "./theme/tokens.json";
import { Grain, MeshBackground } from "@/components/atmosphere";
import { SiteNav } from "@/components/site-nav";

export const metadata: Metadata = {
  title: { default: "serpman studio", template: "%s · serpman studio" },
  description: "Describe a site. A taste engine picks its recipe; an agent builds it. Private research demo.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = { themeColor: "#FFF6FB", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${headingFont.variable} ${bodyFont.variable}`}>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-full focus:bg-surface focus:px-4 focus:py-2">
          Skip to content
        </a>
        <MeshBackground />
        <SiteNav />
        <main id="main">{children}</main>
        <footer className="container-x mt-32 border-t border-line py-10 text-muted">
          <p>
            serpman studio. Theme, header, footer and About page composed by our own engine from the{" "}
            {tokens.source.family} family. A private research demo: reference images belong to their authors.
          </p>
        </footer>
        <Grain />
      </body>
    </html>
  );
}
