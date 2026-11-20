import type { CSSProperties } from "react";
import { cx } from "@/components/ui";

/**
 * Cosmogon Labs' retro-cosmic artwork: the 1976 print language (sunbursts, U-bend rainbow ribbons, sun arches,
 * die-cut stickers, masking tape) applied to a small cosmos. Pure inline SVG, palette variables only, aria-hidden.
 * Motion comes from CSS classes (.drift / .bob / .spin-slow) and stops under prefers-reduced-motion.
 */

const RIBBON = ["var(--cerulean)", "var(--gold)", "var(--rust)", "var(--parch)"];
const RAYS = ["var(--label)", "#6C6D6B", "var(--gold)", "#6C6D6B", "var(--peach)", "#6C6D6B"];

/** 24 alternating rays fading out from the centre (the hero's backdrop). */
export function Sunburst({ className, style, opacity = 0.16 }: { className?: string; style?: CSSProperties; opacity?: number }) {
  const rays = Array.from({ length: 24 }, (_, i) => {
    const a0 = (i / 24) * Math.PI * 2 - Math.PI / 2;
    const a1 = ((i + 1) / 24) * Math.PI * 2 - Math.PI / 2;
    const p = (a: number) => `${(400 * Math.cos(a)).toFixed(1)},${(400 * Math.sin(a)).toFixed(1)}`;
    return <polygon key={i} points={`0,0 ${p(a0)} ${p(a1)}`} fill={RAYS[i % RAYS.length]} />;
  });
  return (
    <svg viewBox="0 0 800 800" aria-hidden="true" focusable="false" className={cx("decor", className)}
      style={{ WebkitMaskImage: "radial-gradient(circle, #000 22%, transparent 68%)", maskImage: "radial-gradient(circle, #000 22%, transparent 68%)", ...style }}>
      <g transform="translate(400 400)" opacity={opacity}>{rays}</g>
    </svg>
  );
}

/** The four-band U-bend ribbon flush to a page edge, read as an orbit sweeping in from outside the frame. */
export function OrbitRibbon({ side = "left", className, style }: { side?: "left" | "right"; className?: string; style?: CSSProperties }) {
  const radii = [130, 104, 78, 52];
  return (
    <svg viewBox="0 0 300 320" fill="none" aria-hidden="true" focusable="false" className={cx("decor", className)} style={style}>
      <g transform={side === "right" ? "translate(300 0) scale(-1 1)" : undefined}>
        {radii.map((r, i) => (
          <path key={r} d={`M -20 ${160 - r} H 150 A ${r} ${r} 0 0 1 150 ${160 + r} H -20`} stroke={RIBBON[i]} strokeWidth="26" />
        ))}
      </g>
    </svg>
  );
}

/** A striped planet with a two-band ring (the back half drawn behind the globe, the front half over it). */
export function RingedPlanet({ className, style, tilt = -18 }: { className?: string; style?: CSSProperties; tilt?: number }) {
  const bands = ["var(--gold-light)", "var(--gold)", "var(--peach)", "var(--coral)", "var(--rust)", "var(--peach)", "var(--gold)"];
  return (
    <svg viewBox="0 0 240 240" aria-hidden="true" focusable="false" className={cx("decor", className)} style={style}>
      <defs>
        <clipPath id="cg-globe"><circle cx="120" cy="120" r="62" /></clipPath>
        <clipPath id="cg-front"><rect x="0" y="120" width="240" height="120" /></clipPath>
      </defs>
      <g transform={`rotate(${tilt} 120 120)`}>
        <ellipse cx="120" cy="120" rx="108" ry="28" fill="none" stroke="var(--teal)" strokeWidth="10" />
        <ellipse cx="120" cy="120" rx="92" ry="21" fill="none" stroke="var(--cerulean)" strokeWidth="7" />
        <g clipPath="url(#cg-globe)">
          {bands.map((c, i) => <rect key={i} x="40" y={58 + i * 18} width="160" height="18" fill={c} />)}
        </g>
        <circle cx="120" cy="120" r="62" fill="none" stroke="var(--espresso)" strokeWidth="3" />
        <g clipPath="url(#cg-front)">
          <ellipse cx="120" cy="120" rx="108" ry="28" fill="none" stroke="var(--teal)" strokeWidth="10" />
          <ellipse cx="120" cy="120" rx="92" ry="21" fill="none" stroke="var(--cerulean)" strokeWidth="7" />
        </g>
      </g>
    </svg>
  );
}

/** Five concentric half-discs: the rising sun behind a headline. */
export function SunArch({ className, style }: { className?: string; style?: CSSProperties }) {
  const rings = ["var(--blush)", "var(--peach)", "#F3963F", "var(--gold)", "#C59A38"];
  return (
    <svg viewBox="0 0 340 170" aria-hidden="true" focusable="false" className={cx("decor", className)} style={style}>
      {rings.map((c, i) => {
        const r = 160 - i * 28;
        return <path key={c} d={`M ${170 - r} 170 A ${r} ${r} 0 0 1 ${170 + r} 170 Z`} fill={c} />;
      })}
    </svg>
  );
}

/** A four-point sparkle. */
export function Sparkle({ className, style, color = "var(--gold)" }: { className?: string; style?: CSSProperties; color?: string }) {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false" className={cx("decor", className)} style={style}>
      <path d="M20 0 C22 13 27 18 40 20 C27 22 22 27 20 40 C18 27 13 22 0 20 C13 18 18 13 20 0 Z" fill={color} />
    </svg>
  );
}

/** The die-cut sticker: white border, chocolate base, dashed cream ring, gold script. */
export function Sticker({ top, script, big, className, style }: { top: string; script: string; big: string; className?: string; style?: CSSProperties }) {
  return (
    <svg viewBox="0 0 140 140" aria-hidden="true" focusable="false" className={cx("decor", className)}
      style={{ filter: "drop-shadow(0 8px 14px rgba(61,34,20,.28))", ...style }}>
      <circle cx="70" cy="70" r="65" fill="#FFFFFF" />
      <circle cx="70" cy="70" r="57" fill="var(--chocolate)" />
      <circle cx="70" cy="70" r="50" fill="none" stroke="var(--cream)" strokeWidth="2" strokeDasharray="4 3" />
      <text x="70" y="52" textAnchor="middle" fill="var(--cream)" style={{ fontFamily: "var(--ui)", fontWeight: 800, fontSize: 9.5, letterSpacing: 1.8 }}>{top}</text>
      <text x="70" y="76" textAnchor="middle" fill="var(--gold-light)" style={{ fontFamily: "var(--script)", fontSize: 18 }}>{script}</text>
      <text x="70" y="102" textAnchor="middle" fill="var(--gold-light)" style={{ fontFamily: "var(--display)", fontWeight: 900, fontSize: 22 }}>{big}</text>
    </svg>
  );
}

/** The small brand glyph next to the wordmark. */
export function PlanetGlyph({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" aria-hidden="true" focusable="false" className={className}>
      <defs><clipPath id="cg-glyph"><circle cx="20" cy="20" r="11" /></clipPath></defs>
      <g transform="rotate(-20 20 20)">
        <g clipPath="url(#cg-glyph)">
          <rect x="8" y="8" width="24" height="6" fill="var(--gold)" />
          <rect x="8" y="14" width="24" height="6" fill="var(--coral)" />
          <rect x="8" y="20" width="24" height="6" fill="var(--rust)" />
          <rect x="8" y="26" width="24" height="6" fill="var(--gold)" />
        </g>
        <circle cx="20" cy="20" r="11" fill="none" stroke="var(--charcoal)" strokeWidth="1.6" />
        <ellipse cx="20" cy="20" rx="18.5" ry="5" fill="none" stroke="var(--teal)" strokeWidth="2.4" />
      </g>
    </svg>
  );
}

/** Masking tape: a full-width crinkled divider, or a short piece pinning a print. */
export function Tape({ className, style }: { className?: string; style?: CSSProperties }) {
  return <div aria-hidden="true" className={cx("tape", className)} style={style} />;
}

export function TapePiece({ className, style }: { className?: string; style?: CSSProperties }) {
  return <span aria-hidden="true" className={cx("tape-piece", className)} style={style} />;
}

/** The hero's cosmos: sunburst, flanking orbit ribbons, a planet and sparkles, all behind the content. */
export function HeroCosmos({ planet = true }: { planet?: boolean }) {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
      <div className="absolute left-1/2 top-[-150px] h-[820px] w-[820px]" style={{ marginLeft: -410 }}>
        <Sunburst className="spin-slow inset-0 h-full w-full" />
      </div>
      <OrbitRibbon side="left" className="drift hide-sm left-[-2px] top-[150px] w-[19vw] min-w-[130px] max-w-[280px]" />
      <OrbitRibbon side="right" className="drift-slow hide-sm right-[-2px] top-[150px] w-[19vw] min-w-[130px] max-w-[280px]" />
      {planet && <RingedPlanet className="bob hide-sm right-[12%] top-[34px] w-[148px]" style={{ ["--r" as string]: "-6deg" }} />}
      <Sparkle className="drift left-[8%] top-[64px] w-6 sm:left-[14%] sm:top-[80px] sm:w-7" />
      <Sparkle className="drift-slow hide-sm left-[24%] top-[300px] w-4" color="var(--teal)" />
      <Sparkle className="bob hide-sm right-[22%] top-[330px] w-5" color="var(--coral)" />
      <Sparkle className="bob right-[6%] top-[96px] w-4 sm:hidden" color="var(--teal)" />
      <Sparkle className="drift hide-sm right-[8%] top-[470px] w-6" color="var(--cerulean)" />
    </div>
  );
}
