import type { ComponentProps, ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function GlassCard({ className, ...p }: ComponentProps<"div">) {
  return <div className={cx("glass p-6 md:p-8", className)} {...p} />;
}

/** Display type: the lab's heading face, italic when the vibe asks for it, sized from the type scale. */
export function Display({ as: As = "h2", step = 6, className, children }: { as?: "h1" | "h2" | "h3"; step?: 3 | 4 | 5 | 6 | 7 | 8; className?: string; children: ReactNode }) {
  const size = { 3: "text-step-3", 4: "text-step-4", 5: "text-step-5", 6: "text-step-6", 7: "text-step-7", 8: "text-step-8" }[step];
  return <As className={cx("display font-heading text-ink", size, className)}>{children}</As>;
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("eyebrow mb-3", className)}>{children}</p>;
}

export function Float({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <div className={cx("float", className)} style={{ animationDelay: `${delay}s` }}>
      {children}
    </div>
  );
}

export function SwatchRow({ colors, size = "md" }: { colors: string[]; size?: "sm" | "md" }) {
  const s = size === "sm" ? "h-6 w-6" : "h-10 w-10";
  return (
    <ul className="flex flex-wrap gap-2" aria-label="palette">
      {colors.map((c) => (
        <li key={c} className="flex flex-col items-center gap-1">
          <span className={cx(s, "rounded-full border border-line shadow-sm")} style={{ background: c }} />
          {size === "md" && <span className="font-mono text-[11px] text-muted">{c}</span>}
        </li>
      ))}
    </ul>
  );
}

/** Loads the font from Google Fonts on demand (app CSP allows fonts.googleapis.com) and shows a specimen. */
export function FontSpecimen({ family, role, css, italic }: { family: string; role: string; css?: string; italic?: boolean }) {
  return (
    <div className="min-w-0">
      {css && <link rel="stylesheet" href={css} />}
      <p className="eyebrow mb-1">{role}</p>
      <p className="truncate text-step-5 leading-tight text-ink" style={{ fontFamily: `"${family}", serif`, fontStyle: italic ? "italic" : "normal" }}>
        Aa Gg Rr
      </p>
      <p className="mt-1 text-muted">{family}</p>
    </div>
  );
}

export function Chip({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "accent" | "warn" }) {
  return (
    <span
      className={cx(
        "inline-flex items-center rounded-full border px-3 py-1 text-[13px]",
        tone === "accent" && "border-transparent bg-accent text-on-accent",
        tone === "warn" && "border-line bg-surface text-ink",
        tone === "plain" && "border-line bg-surface/50 text-muted",
      )}
    >
      {children}
    </span>
  );
}
