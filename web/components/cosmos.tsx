import type { CSSProperties } from "react";
import { cx } from "@/components/ui";

/**
 * Cosmogon Labs' print furniture. Textures are real 1970s abstract prints from the corpus
 * (70s-80s-retro / c05 abstract art, copied to /public/textures); they only ever fill non-text space.
 */

export type TextureName = "wave" | "stripes" | "rings" | "tiles" | "arch";

/** A block filled with one of the retro prints (decorative: aria-hidden, never carries text). */
export function Texture({ name, className, style, position }: { name: TextureName; className?: string; style?: CSSProperties; position?: string }) {
  return <div aria-hidden="true" className={cx("texture", `tex-${name}`, className)} style={{ backgroundPosition: position, ...style }} />;
}

/** The thin printed strip under the header and above the footer. */
export function Strip({ name = "stripes", className, position = "center 38%" }: { name?: TextureName; className?: string; position?: string }) {
  return <Texture name={name} position={position} className={cx("strip", className)} />;
}

/** A framed print with a hard ink offset (the retro web kit's poster panel). */
export function Poster({ name, caption, className, artClassName, position }: { name: TextureName; caption?: string; className?: string; artClassName?: string; position?: string }) {
  return (
    <figure className={cx("poster m-0", className)}>
      <Texture name={name} position={position} className={cx("art", artClassName)} />
      {caption && <figcaption className="meta mt-3 flex items-center justify-between gap-3"><span>{caption}</span><span aria-hidden="true">No. 70</span></figcaption>}
    </figure>
  );
}

/** The brand mark: a forest disc with a gold ring and a cream C. */
export function Monogram({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 44 44" aria-hidden="true" focusable="false" className={className}>
      <circle cx="22" cy="22" r="19" fill="var(--forest)" stroke="var(--ink)" strokeWidth="2" />
      <circle cx="22" cy="22" r="14.5" fill="none" stroke="var(--gold)" strokeWidth="2.5" />
      <text x="22" y="29.5" textAnchor="middle" fill="var(--cream)"
        style={{ fontFamily: "var(--display)", fontWeight: 900, fontStyle: "italic", fontSize: 21 }}>C</text>
    </svg>
  );
}

/** A short piece of masking tape pinning a card. */
export function TapePiece({ className, style }: { className?: string; style?: CSSProperties }) {
  return <span aria-hidden="true" className={cx("tape-piece", className)} style={style} />;
}
