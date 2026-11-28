import type { MetadataRoute } from "next";
import { SITE_DESC, SITE_NAME } from "@/lib/seo";

// Same icons as app/favicon.ico, icon.png and apple-icon.png, for browsers, installs and crawlers.
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: SITE_NAME,
    short_name: "Cosmogon",
    description: SITE_DESC,
    start_url: "/",
    display: "standalone",
    background_color: "#FBF5EF",
    theme_color: "#FBF5EF",
    icons: [
      { src: "/favicon.ico", sizes: "16x16 32x32 48x48", type: "image/x-icon" },
      { src: "/icon.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/apple-icon.png", sizes: "180x180", type: "image/png" },
    ],
  };
}
