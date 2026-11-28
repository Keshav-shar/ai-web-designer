import type { NextConfig } from "next";

const supabase = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

// App-wide headers. Generated sites are rendered in a sandboxed srcdoc iframe (no scripts, opaque origin) and
// the full-tab preview route sets its own stricter CSP with the `sandbox` directive.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'" + (process.env.NODE_ENV === "development" ? " 'unsafe-eval'" : ""),
  // srcdoc previews inherit this policy, and their stylesheet is a signed Storage URL
  `style-src 'self' 'unsafe-inline' https://fonts.googleapis.com ${supabase}`,
  "font-src 'self' https://fonts.gstatic.com",
  `img-src 'self' data: blob: ${supabase}`,
  `connect-src 'self' ${supabase} ${supabase.replace("https://", "wss://")}`,
  "frame-src 'self'",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const config: NextConfig = {
  poweredByHeader: false,
  async redirects() {
    return [{ source: "/studio", destination: "/", permanent: true }];
  },
  async headers() {
    return [
      {
        source: "/((?!sites/[^/]+/preview).*)",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
      // personal areas and the engine API: never indexed, even if a link leaks (route handlers have no HTML meta)
      // AI-only context (/ai, /llms.txt): crawlable for AI bots, kept out of search results. robots.txt must keep
      // allowing these, or Google never sees this header and indexes the bare URL anyway.
      ...["/sites/:path*", "/api/:path*", "/auth/:path*", "/login", "/ai", "/llms.txt"].map((source) => ({
        source,
        headers: [{ key: "X-Robots-Tag", value: "noindex, nofollow" }],
      })),
    ];
  },
};

export default config;
