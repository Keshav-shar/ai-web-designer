import type { ReactNode } from "react";
import { cx } from "@/components/ui";

/**
 * Dependency-free chart primitives for /evidence: HTML bars and dots on the cream card surface, so labels stay
 * real text at every width.
 * Series colours were validated with the dataviz skill's validate_palette.js (light, surface #F6EEE9), and each
 * gains contrast on the cream #FBF4EA surface used now (s1 4.2, s2 3.2, s3 5.1, s4 4.9 :1):
 * s1 #00866A, s2 #C07A2C, s3 #A2477E, s4 #4A68B0 pass lightness, chroma, CVD, normal-vision and contrast checks.
 * `base` is the de-emphasis grey for a comparison series. Text always wears text tokens, never a series colour.
 *
 * Layout contract: every chart is a 2-column grid (label | plot) on >= sm, label above plot on phones. The plot
 * column reserves `GUTTER` on the right for value labels; everything positioned inside a plot uses a `relative`
 * wrapper that spans exactly the scale's 0..max, so bars, dots, ticks and reference lines share one x scale.
 */
export const SERIES = { s1: "#00866A", s2: "#C07A2C", s3: "#A2477E", s4: "#4A68B0", base: "#B9A9A4" } as const;
export const SURFACE = "#FBF4EA";
const GRID = "#E6DCCB";
const REF = "#6B5547";
const GUTTER = "pr-16";

type Ref = { at: number; label: string };
type Scale = { min?: number; max: number; log?: boolean };
const at = (v: number, { min = 0, max, log }: Scale) => {
  const f = log ? (Math.log(v) - Math.log(min)) / (Math.log(max) - Math.log(min)) : (v - min) / (max - min);
  return `${Math.max(0, Math.min(100, f * 100))}%`;
};

const BAR_OF: Record<string, string> = { curation: "avocado", representation: "rust", routing: "teal", text: "gold",
  contrast: "cerulean", corrections: "avocado", placement: "rust", gate: "teal" };

export const fmt = (v: number) => v.toLocaleString("en-US");
export const fmtPct = (v: number, d = 0) => `${(v * 100).toFixed(d)}%`;

export function ChartCard({ id, kicker, title, shows, n, children, table }: {
  id: string; kicker: string; title: string; shows: ReactNode; n: ReactNode; children: ReactNode; table?: ReactNode;
}) {
  return (
    <section id={id} aria-labelledby={`${id}-t`} className="card scroll-mt-24 overflow-hidden">
      <div aria-hidden="true" className={`card-bar bar-${BAR_OF[id] ?? "gold"}`} />
      <div className="p-5 sm:p-8">
      <p className="eyebrow">{kicker}</p>
      <h2 id={`${id}-t`} className="display display-3">{title}</h2>
      <div className="mt-4 max-w-[64ch] text-espresso">{shows}</div>
      <div className="mt-8">{children}</div>
      <p className="mt-6 text-[13px] text-muted">{n}</p>
      {table && (
        <details className="mt-3 text-[14px]">
          <summary className="cursor-pointer text-muted hover:text-ink">Table view</summary>
          <div className="mt-3 overflow-x-auto">{table}</div>
        </details>
      )}
      </div>
    </section>
  );
}

export function Legend({ items }: { items: { label: string; color: string; shape?: "bar" | "dot" }[] }) {
  return (
    <ul className="mb-6 flex flex-wrap gap-x-5 gap-y-2 text-[14px] text-ink" aria-label="Legend">
      {items.map((i) => (
        <li key={i.label} className="flex items-center gap-2">
          <span aria-hidden className={i.shape === "dot" ? "h-3 w-3 rounded-full" : "h-3 w-5 rounded-[3px]"} style={{ background: i.color }} />
          {i.label}
        </li>
      ))}
    </ul>
  );
}

// ------------------------------------------------------------------ layout pieces
function Grid({ wide, children }: { wide?: boolean; children: ReactNode }) {
  return (
    <div className={cx("grid gap-y-2 sm:items-center sm:gap-x-5 sm:gap-y-4",
      wide ? "sm:grid-cols-[minmax(11rem,17rem)_1fr]" : "sm:grid-cols-[minmax(10rem,14rem)_1fr]")}>
      {children}
    </div>
  );
}

function Row({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <>
      <div className="mt-2 text-[14px] leading-snug text-ink sm:mt-0 sm:text-right">{label}</div>
      <div className={GUTTER}><div className="relative">{children}</div></div>
    </>
  );
}

/** Reference-line labels above the plot (hidden spacer in the label column). */
function RefLabels({ refs, s }: { refs?: Ref[]; s: Scale }) {
  if (!refs?.length) return null;
  return (
    <>
      <div className="hidden sm:block" />
      <div className={GUTTER}><div className="relative h-5">
        {refs.map((r) => (
          <span key={r.label} className="absolute -translate-x-1/2 whitespace-nowrap text-[12px] text-muted" style={{ left: at(r.at, s) }}>{r.label}</span>
        ))}
      </div></div>
    </>
  );
}

function RefLines({ refs, s }: { refs?: Ref[]; s: Scale }) {
  return (
    <>
      {refs?.map((r) => (
        <div key={r.label} aria-hidden className="pointer-events-none absolute -bottom-2 -top-2 w-px" style={{ left: at(r.at, s), background: REF }} />
      ))}
    </>
  );
}

function Ticks({ ticks, s, f }: { ticks?: number[]; s: Scale; f?: (v: number) => string }) {
  if (!ticks?.length) return null;
  return (
    <>
      <div className="hidden sm:block" />
      <div className={GUTTER}><div aria-hidden className="relative mt-1 h-4 border-t text-[11px] tabular-nums text-muted" style={{ borderColor: GRID }}>
        {ticks.map((t) => <span key={t} className="absolute top-1 -translate-x-1/2" style={{ left: at(t, s) }}>{(f ?? String)(t)}</span>)}
      </div></div>
    </>
  );
}

function Bar({ v, s, color, title, label }: { v: number; s: Scale; color: string; title: string; label: string }) {
  return (
    <div className="relative h-[14px]">
      <div className="h-full rounded-r-[4px]" style={{ width: at(v, s), background: color, minWidth: v > 0 ? 3 : 0 }} title={title} />
      <span className="pointer-events-none absolute top-1/2 -translate-y-1/2 whitespace-nowrap pl-2 text-[12px] leading-none tabular-nums text-ink"
        style={{ left: at(v, s) }}>{label}</span>
    </div>
  );
}

function Dot({ v, s, color, title }: { v: number; s: Scale; color: string; title: string }) {
  return (
    <span title={title} className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full"
      style={{ left: at(v, s), background: color, boxShadow: `0 0 0 2px ${SURFACE}` }} />
  );
}

// ------------------------------------------------------------------ charts
type Axis = { min?: number; max: number; log?: boolean; refs?: Ref[]; ticks?: number[]; fmtTick?: (v: number) => string };

/** One measure per row; `color` per row lets a class of rows carry emphasis (the rest in `base`). */
export function BarList({ rows, fmtValue = fmt, ...ax }: Axis & {
  rows: { label: ReactNode; value: number; color: string; title?: string }[]; fmtValue?: (v: number) => string;
}) {
  return (
    <Grid>
      <RefLabels refs={ax.refs} s={ax} />
      {rows.map((r, i) => (
        <Row key={i} label={r.label}>
          <Bar v={r.value} s={ax} color={r.color} title={r.title ?? fmtValue(r.value)} label={fmtValue(r.value)} />
          <RefLines refs={ax.refs} s={ax} />
        </Row>
      ))}
      <Ticks ticks={ax.ticks} s={ax} f={ax.fmtTick} />
    </Grid>
  );
}

/** Two or more series per category, bars 2px apart; the caller renders the Legend. */
export function GroupedBars({ rows, series, fmtValue = fmt, ...ax }: Axis & {
  rows: { label: ReactNode; values: number[] }[]; series: { label: string; color: string }[]; fmtValue?: (v: number) => string;
}) {
  return (
    <Grid>
      <RefLabels refs={ax.refs} s={ax} />
      {rows.map((r, i) => (
        <Row key={i} label={r.label}>
          <div className="flex flex-col gap-[2px]">
            {r.values.map((v, k) => (
              <Bar key={k} v={v} s={ax} color={series[k].color} title={`${series[k].label}: ${fmtValue(v)}`} label={fmtValue(v)} />
            ))}
          </div>
          <RefLines refs={ax.refs} s={ax} />
        </Row>
      ))}
      <Ticks ticks={ax.ticks} s={ax} f={ax.fmtTick} />
    </Grid>
  );
}

/** One row per category, one dot per observation on a shared scale. */
export function DotStrip({ rows, color, ...ax }: Axis & {
  rows: { label: ReactNode; points: { v: number; title: string; color?: string }[]; note?: string }[]; color: string;
}) {
  return (
    <Grid>
      <RefLabels refs={ax.refs} s={ax} />
      {rows.map((r, i) => (
        <Row key={i} label={r.label}>
          <div className="relative h-5">
            <div aria-hidden className="absolute inset-x-0 top-1/2 h-px" style={{ background: GRID }} />
            <RefLines refs={ax.refs} s={ax} />
            {r.points.map((p, k) => <Dot key={k} v={p.v} s={ax} color={p.color ?? color} title={p.title} />)}
            {r.note && (
              <span className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 whitespace-nowrap pl-2 text-[12px] tabular-nums text-ink">{r.note}</span>
            )}
          </div>
        </Row>
      ))}
      <Ticks ticks={ax.ticks} s={ax} f={ax.fmtTick} />
    </Grid>
  );
}

/** Before -> after on one scale: `before` dot, a connector, `after` dot, values at the right end. */
export function Dumbbell({ rows, before, after, ...ax }: Axis & {
  rows: { label: ReactNode; a: number; b: number; title: string; target?: number; afterColor?: string }[]; before: string; after: string;
}) {
  return (
    <Grid wide>
      <RefLabels refs={ax.refs} s={ax} />
      {rows.map((r, i) => {
        const lo = Math.min(r.a, r.b), hi = Math.max(r.a, r.b);
        return (
          <Row key={i} label={r.label}>
            <div className="relative h-6" title={r.title}>
              <RefLines refs={ax.refs} s={ax} />
              {r.target != null && (
                <div aria-hidden className="absolute -bottom-1 -top-1 w-[2px] -translate-x-1/2 rounded-full" style={{ left: at(r.target, ax), background: REF }} title={`target ${r.target}:1`} />
              )}
              <div aria-hidden className="absolute top-1/2 h-[2px] -translate-y-1/2"
                style={{ left: at(lo, ax), width: `calc(${at(hi, ax)} - ${at(lo, ax)})`, background: "#8E7F83" }} />
              <Dot v={r.a} s={ax} color={before} title={`before ${r.a.toFixed(2)}:1`} />
              <Dot v={r.b} s={ax} color={r.afterColor ?? after} title={`after ${r.b.toFixed(2)}:1`} />
              <span className="pointer-events-none absolute top-1/2 -translate-y-1/2 whitespace-nowrap pl-3 text-[12px] tabular-nums text-ink" style={{ left: at(Math.max(hi, r.target ?? 0), ax) }}>
                {r.a.toFixed(1)} → {r.b.toFixed(1)}
              </span>
            </div>
          </Row>
        );
      })}
      <Ticks ticks={ax.ticks} s={ax} f={ax.fmtTick} />
    </Grid>
  );
}

/** Tall segmented bar per row (parts of one whole), the count printed inside when it fits; caller renders the Legend. */
export function StackedBars({ rows, series }: { rows: { label: ReactNode; values: number[] }[]; series: { label: string; color: string }[] }) {
  return (
    <Grid>
      {rows.map((r, i) => {
        const total = r.values.reduce((a, b) => a + b, 0) || 1;
        return (
          <Row key={i} label={r.label}>
            <div className="flex h-7 gap-[2px]" role="img" aria-label={series.map((s, k) => `${s.label} ${r.values[k]}`).join(", ")}>
              {r.values.map((v, k) => v > 0 && (
                <div key={k} title={`${series[k].label}: ${v} of ${total}`}
                  className="flex items-center rounded-[4px] px-1.5 text-[12px] font-medium tabular-nums text-white"
                  style={{ width: `${(v / total) * 100}%`, background: series[k].color }}>
                  {v / total >= 0.08 ? v : ""}
                </div>
              ))}
            </div>
            <span className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 whitespace-nowrap pl-2 text-[12px] tabular-nums text-muted">{total}</span>
          </Row>
        );
      })}
    </Grid>
  );
}

export function Stat({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="min-w-0">
      <p className="text-[13px] text-muted">{label}</p>
      <p className="mt-2 font-display text-[2.1rem] font-black leading-none text-sienna">{value}</p>
      {sub && <p className="mt-1.5 text-[13px] text-muted">{sub}</p>}
    </div>
  );
}

export function Table({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="w-full min-w-[28rem] border-collapse text-left text-[13px] text-ink">
      <thead><tr>{head.map((h) => <th key={h} className="border-b border-line py-1.5 pr-4 font-medium">{h}</th>)}</tr></thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i}>{r.map((c, k) => (
            <td key={k} className={cx("border-b py-1.5 pr-4", typeof c === "number" && "tabular-nums")} style={{ borderColor: GRID }}>{c}</td>
          ))}</tr>
        ))}
      </tbody>
    </table>
  );
}

export function Swatch({ hex }: { hex: string }) {
  return <span aria-hidden className="inline-block h-3.5 w-3.5 rounded-full align-[-2px]" style={{ background: hex, boxShadow: `0 0 0 1px ${GRID}` }} />;
}
