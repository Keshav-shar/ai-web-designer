import type { ComponentProps, ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export const BARS = ["avocado", "rust", "teal"] as const;
export type Bar = (typeof BARS)[number] | "gold" | "cerulean";

/** A printed card: cream stock, espresso hairline, an optional coloured top bar. */
export function Card({ bar, lift, className, children, ...p }: ComponentProps<"div"> & { bar?: Bar; lift?: boolean }) {
  return (
    <div className={cx("card", lift && "card-lift", className)} {...p}>
      {bar && <div aria-hidden="true" className={`card-bar bar-${bar}`} />}
      {children}
    </div>
  );
}

/** Display type: Fraunces black, sienna, three sizes. */
export function Display({ as: As = "h2", size = 2, className, children }: { as?: "h1" | "h2" | "h3"; size?: 1 | 2 | 3; className?: string; children: ReactNode }) {
  return <As className={cx("display", `display-${size}`, className)}>{children}</As>;
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("eyebrow", className)}>{children}</p>;
}

export function Tag({ children, tone = "line" }: { children: ReactNode; tone?: "avocado" | "rust" | "teal" | "gold" | "line" }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}
