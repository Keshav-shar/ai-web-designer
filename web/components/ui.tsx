import type { ComponentProps, ReactNode } from "react";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export const BARS = ["forest", "gold", "vermilion"] as const;
export type Bar = (typeof BARS)[number] | "orange" | "teal";

/** A printed card: cream stock, a 2px ink border, a hard ink offset, an optional coloured top bar. */
export function Card({ bar, lift, flat, className, children, ...p }: ComponentProps<"div"> & { bar?: Bar; lift?: boolean; flat?: boolean }) {
  return (
    <div className={cx("card", lift && "card-lift", flat && "card-flat", className)} {...p}>
      {bar && <div aria-hidden="true" className={`card-bar bar-${bar}`} />}
      {children}
    </div>
  );
}

/** Display type: Fraunces black, forest, three sizes. */
export function Display({ as: As = "h2", size = 2, className, children }: { as?: "h1" | "h2" | "h3"; size?: 1 | 2 | 3; className?: string; children: ReactNode }) {
  return <As className={cx("display", `display-${size}`, className)}>{children}</As>;
}

export function Eyebrow({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("eyebrow", className)}>{children}</p>;
}

export function Tag({ children, tone = "line" }: { children: ReactNode; tone?: "forest" | "gold" | "cta" | "line" }) {
  return <span className={`tag tag-${tone}`}>{children}</span>;
}
