"use client";
import { Fragment, type CSSProperties } from "react";
import { Monogram, Poster, Strip, TapePiece } from "@/components/cosmos";
import { cx } from "@/components/ui";
import {
  AGENTS, CHECKS, DOC_LINES, FAMILIES, FUNNEL, GATE, LAYERS, PALETTE, QUERY, REFS, SEARCHES, SPLIT, fmt,
} from "@/content/pipeline";
import { useCountUp } from "./timeline";
import { CLUSTER, type Tile } from "./tiles";

/** Scene indices (0-based) — the order of SCENES in content/pipeline.ts. */
export const S = {
  serp: 0, pool: 1, cluster: 2, clip: 3, dock: 4, query: 5, refs: 6, attach: 7, breakdown: 8,
  nonvlm: 9, layers: 10, compose: 11, cosmogon: 12,
} as const;

type P = { scene: number; rm: boolean };
type Box = { x: number; y: number; w: number; h: number };

/* Elements are placed with left/top so the per-scene pops (individual `scale`/`translate`) stay local. */
const at = (x: number, y: number, transform?: string): CSSProperties => ({ left: x, top: y, transform });
const d = (s: number): CSSProperties => ({ animationDelay: `${s}s` });
/** Delay inside an agent station, counted from that station's entrance (--d0). */
const dv = (s: number): CSSProperties => ({ animationDelay: `calc(var(--d0) + ${s}s)` });
const vis = (on: boolean) => (on ? "pl-on" : "pl-off");
const vars = (v: Record<string, string | number>) => v as CSSProperties;
const hex = (name: string) => PALETTE.find((c) => c.name === name)!.hex;

const PINE = hex("Pine Ink"), MARIGOLD = hex("Marigold"), TANGERINE = hex("Tangerine"), VERMILION = hex("Signal Vermilion");
const CORAL = hex("Blush Coral"), SAGE = hex("Sage Mint"), ESPRESSO = hex("Espresso"), RUST = hex("Sunburst Rust");
const GREY = hex("Ray Grey"), LINEN = hex("Linen"), DEEP = "#002520";

/* ------------------------------------------------------------------------------------------- Act I: the engine */

const HITS = SEARCHES.map((q, i) => {
  const x = i % 2 ? 940 : 700;
  const y = 50 + Math.floor(i / 2) * 150;
  return { q, x, y, path: `M300 335 C 470 335, ${x - 170} ${y + 55}, ${x} ${y + 55}` };
});

export function EngineLayer({ scene, rm, tiles, cream }: P & { tiles: Tile[]; cream: Box }) {
  const s = scene;
  const transform = s >= S.attach ? "translate(16px, 16px) scale(.2)"
    : s >= S.query ? "translate(20px, 236px) scale(.3)"
    : s >= S.dock ? "translate(170px, 110px) scale(.5)" : "none";
  return (
    <div className={cx("pl-engine", s >= S.cosmogon && "pl-gone")} style={{ transform }}>
      <div className={cx("pl-abs pl-dock", vis(s >= S.dock))} />

      {/* the SERP engine block */}
      <div className="pl-abs pl-serp" style={at(50, 190)}>
        <svg className="pl-dial" viewBox="0 0 100 100" aria-hidden="true">
          <circle cx="50" cy="50" r="44" fill="none" stroke={MARIGOLD} strokeWidth="6" strokeDasharray="10 7" />
          <circle cx="50" cy="50" r="30" fill="none" stroke="var(--cream)" strokeWidth="3" />
          <path d="M50 50 L50 14" stroke="var(--vermilion)" strokeWidth="6" strokeLinecap="round" />
          <circle cx="50" cy="50" r="7" fill="var(--cream)" />
        </svg>
        <div className="pl-serp-word">SERP</div>
        <div className="pl-serp-sub">engine</div>
        <div className="pl-serp-meta">public design search · fan-out</div>
      </div>

      {/* links out to result pages, and images riding back */}
      <svg className={cx("pl-svg pl-links", vis(s === S.serp))} viewBox="0 0 1200 675" aria-hidden="true">
        {HITS.map((h, i) => (
          <path key={h.q} d={h.path} pathLength={1} className={cx(s === S.serp && "pl-draw")} style={d(0.3 + i * 0.15)} />
        ))}
      </svg>
      {HITS.map((h, i) => (
        <div key={h.q} className={cx("pl-abs pl-hit", vis(s === S.serp), s === S.serp && "pl-pop")} style={{ ...at(h.x, h.y), ...d(0.7 + i * 0.15) }}>
          <div className="pl-hit-bar"><i /><i /><i /><span>{h.q}</span></div>
          <div className="pl-hit-body">
            {[0, 1, 2].map((j) => <i key={j} style={{ background: FAMILIES[(i * 5 + j * 7) % FAMILIES.length].colors[(i + j) % 4] }} />)}
          </div>
        </div>
      ))}
      {s === S.serp && HITS.flatMap((h, i) => [0, 1].map((j) => (
        <i key={`${i}-${j}`} className="pl-ride"
          style={{ offsetPath: `path("${h.path}")`, animationDelay: `${2.3 + i * 0.22 + j * 0.55}s`, background: FAMILIES[(i + j * 5) % FAMILIES.length].colors[j + 1] }} />
      )))}

      <Funnel scene={s} rm={rm} />

      {/* the pool: one tile per ~480 references */}
      {tiles.map((t) => (
        <i key={t.i} className={cx("pl-tile", t.cream && "is-cream")}
          style={vars({
            backgroundColor: t.color, backgroundImage: t.img ? `url(${t.img})` : "none",
            "--px": `${t.px}px`, "--py": `${t.py}px`, "--cx": `${t.cx}px`, "--cy": `${t.cy}px`,
            "--kx": `${t.kx}px`, "--ky": `${t.ky}px`, "--lens": t.lens.toFixed(3), "--pour": t.pour,
          })} />
      ))}

      {FAMILIES.map((f, k) => (
        <div key={f.name} className={cx("pl-abs pl-clabel", vis(s === S.cluster), s === S.clip && "pl-hold")}
          style={at(CLUSTER.x + (k % CLUSTER.cols) * CLUSTER.w + 10, CLUSTER.y + Math.floor(k / CLUSTER.cols) * CLUSTER.h + 8)}>
          {f.name}
        </div>
      ))}
      <div className={cx("pl-abs tag tag-line pl-more", vis(s === S.cluster), s === S.clip && "pl-hold")} style={at(1008, 616)}>
        +27 more families
      </div>

      <div className={cx("pl-abs pl-lens", s === S.clip && "pl-sweep")} style={at(CLUSTER.x - 22, 126)}>
        <span className="tag tag-gold">CLIP</span>
      </div>
      <div className={cx("pl-abs pl-creamlabel", vis(s >= S.clip), s === S.clip && "pl-pop")}
        style={{ ...at(cream.x - 40, cream.y + cream.h + 16), width: cream.w + 80, ...d(4.6) }}>
        Cream layer · each column is one family&rsquo;s strongest
      </div>
      <div className={cx("pl-abs pl-stamp", vis(s >= S.clip), s === S.clip && "pl-stamp-in")} style={{ ...at(cream.x + cream.w + 30, cream.y + 18), ...d(5.3) }}>
        Text-free ✓<small>CLIP check −0.02</small>
      </div>

      <div className={cx("pl-abs pl-dock-title", vis(s >= S.dock))}>
        <span>Core engine</span>
        <small>{fmt(FUNNEL[2].value)} cream refs · zero generative AI</small>
      </div>
    </div>
  );
}

function Funnel({ scene, rm }: P) {
  return (
    <div className={cx("pl-abs pl-funnel", vis(scene >= S.pool && scene < S.dock))} style={at(372, 24)}>
      {FUNNEL.map((f, k) => {
        const on = scene >= S.pool + k;
        return (
          <Fragment key={f.short}>
            {k > 0 && (
              <div className={cx("pl-arrow", vis(on))}>
                <span>{k === 1 ? "cluster" : "CLIP"}</span>
                <svg viewBox="0 0 46 20" aria-hidden="true">
                  <path d="M2 10 H40 M31 3 L41 10 L31 17" pathLength={1} className={cx(scene === S.pool + k && "pl-draw")} />
                </svg>
              </div>
            )}
            <Chip on={on} active={scene === S.pool + k} value={f.value} label={f.short} rm={rm} />
          </Fragment>
        );
      })}
    </div>
  );
}

function Chip({ on, active, value, label, rm }: { on: boolean; active: boolean; value: number; label: string; rm: boolean }) {
  const v = useCountUp(on ? value : 0, 1500, rm);
  return (
    <div className={cx("pl-chip", vis(on), active && "is-active")}>
      <b>{fmt(v)}</b>
      <span>{label}</span>
    </div>
  );
}

/* ------------------------------------------------------------------------------- Acts II–III: serving one query */

const QPATH = "M440 150 C 400 150, 430 341, 384 341";
const ROW = (i: number) => 124 + i * 120;

export function ServeLayer({ scene }: P) {
  const s = scene;
  const qPos = s >= S.breakdown ? at(292, 84, "scale(.5)") : s >= S.attach ? at(352, 210, "scale(.8)") : at(440, 118);
  const a1 = s >= S.breakdown ? { left: 272, top: 20, width: 912, height: 640 } : { left: 330, top: 140, width: 620, height: 380 };
  const frame = s >= S.cosmogon ? { left: 24, top: 24, width: 1152, height: 627 } : { left: 290, top: 40, width: 880, height: 600 };
  return (
    <div className="pl-serve">
      <div className={cx("pl-abs", vis(s >= S.dock && s < S.attach), s === S.dock && "pl-pop")} style={{ ...(s >= S.query ? at(20, 456) : at(170, 470)), ...d(1.1) }}>
        <span className="tag tag-forest">Built offline · once</span>
      </div>

      {/* A1 card sits behind the brief it receives */}
      <div className={cx("pl-abs pl-a1", vis(s === S.attach || s === S.breakdown), s === S.attach && "pl-pop")} style={{ ...a1, ...d(0.2) }}>
        <div className="card-bar bar-forest" />
        <div className="pl-a1-head">
          <b>A1 · Component segregation agent</b>
          <span>visual director · VLM · the only stage that sees images</span>
        </div>
      </div>

      {/* the query */}
      <svg className={cx("pl-svg", vis(s === S.query || s === S.refs))} viewBox="0 0 1200 675" aria-hidden="true">
        <path d={QPATH} pathLength={1} className={cx("pl-link", s === S.query && "pl-draw")} style={d(1.9)} />
      </svg>
      {s === S.query && <i className="pl-token" style={{ offsetPath: `path("${QPATH}")`, animationDelay: "2s" }} />}
      <div className={cx("pl-abs pl-query", vis(s >= S.query && s <= S.breakdown), s === S.query && "pl-pop", s >= S.attach && "is-packed")} style={qPos}>
        <span className="tag tag-forest pl-query-label">User query</span>
        <span className={cx("pl-typed", s === S.query && "pl-type")}>{QUERY}</span>
        <i className="pl-caret" />
      </div>
      {SPLIT.map((x, k) => (
        <div key={x.k} className={cx("pl-abs pl-split", vis(s === S.query || s === S.refs), s === S.query && "pl-pop")}
          style={{ ...at(440, 212 + k * 52), ...d(2.7 + k * 0.35) }}>
          <span className="tag tag-gold">{x.k}</span>{x.v}
        </div>
      ))}

      {/* five labelled references out of the engine */}
      {REFS.map((r, i) => {
        const p = s >= S.breakdown ? { x: 292, y: ROW(i), t: "scale(.8)" }
          : s >= S.attach ? { x: 352 + i * 146, y: 290, t: `scale(.8) rotate(${-3 + i * 2}deg)` }
          : { x: 440 + i * 180, y: 330, t: undefined };
        return (
          <figure key={r.src} className={cx("pl-abs pl-ref", vis(s >= S.refs && s <= S.breakdown), s === S.refs && "pl-fly", s >= S.breakdown && "is-small")}
            style={{ ...at(p.x, p.y, p.t), ...vars({ "--x": `${p.x}px`, "--y": `${p.y}px` }), ...d(0.3 + i * 0.35) }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={r.src} alt="" />
            <figcaption><span className="tag tag-gold">{r.role}</span></figcaption>
          </figure>
        );
      })}
      <div className={cx("pl-abs pl-pal", vis(s === S.refs || s === S.attach), s === S.refs && "pl-pop")}
        style={{ ...(s >= S.attach ? at(352, 428, "scale(.82)") : at(440, 492)), ...d(1.9) }}>
        <div className="pl-pal-row">{PALETTE.map((c) => <i key={c.hex} style={{ background: c.hex }} />)}</div>
        <span className="tag tag-line">Palette · measured from the references</span>
      </div>
      {s === S.attach && <TapePiece className="pl-pop" style={{ left: 896, top: 128, rotate: "10deg", animationDelay: "1.5s" }} />}

      <Breakdown scene={s} />

      {/* the design document (A1 writes it; it travels on) */}
      <div className={cx("pl-abs pl-doc", vis(s === S.breakdown || s === S.nonvlm), s === S.breakdown && "pl-pop")}
        style={{ ...(s >= S.nonvlm ? at(272, 178, "scale(.62)") : at(866, 80)), ...d(0.6) }}>
        <div className="pl-doc-head"><span>design_doc.json</span><span>A1 → A5</span></div>
        <ol>
          {DOC_LINES.map(([k, v], i) => (
            <li key={k} className={cx(s === S.breakdown && "pl-line")} style={d(1.2 + i * 0.42)}>
              <b>{k}</b><span>{v}</span>
            </li>
          ))}
        </ol>
      </div>

      <NonVlm scene={s} />

      {/* the page: layers, wrapped, in a browser */}
      <div className={cx("pl-abs pl-mock", vis(s >= S.compose), s === S.compose && "pl-pop")} style={frame}>
        <div className="pl-chrome">
          <span className="pl-dots"><i style={{ background: "var(--gold)" }} /><i style={{ background: "var(--vermilion)" }} /><i style={{ background: "var(--teal)" }} /></span>
          <span className="pl-url">
            <span className={vis(s < S.cosmogon)}>analog76.fest</span>
            <span className={vis(s >= S.cosmogon)}>cosmogon labs · studio</span>
          </span>
        </div>
      </div>
      <div className={cx("pl-abs pl-planes", vis(s === S.layers || s === S.compose), s === S.cosmogon && "is-leaving")} style={{ left: 292, top: 80, width: 876, height: 558 }}>
        {LAYERS.map((l) => (
          <div key={l.n} className={cx("pl-plane", `pl-plane-${l.n}`, s === S.layers && "pl-wrap")} style={vars({ "--i": l.n, zIndex: l.n })}>
            {l.n === 0 && <RetroBackdrop />}
            {l.n === 1 && <RetroDecor />}
            {l.n === 2 && <RetroContent />}
            {l.n === 3 && <RetroFore />}
            {l.n === 4 && <div className="pl-grain" />}
          </div>
        ))}
      </div>
      {LAYERS.map((l) => (
        <div key={l.n} className={cx("pl-abs pl-llabel pl-off", s === S.layers && "pl-lhold")} style={{ ...at(958, 461 - l.n * 62), ...vars({ "--i": l.n }) }}>
          <b>Layer {l.n} · {l.name}</b>
          <span>{l.z} · {l.what}</span>
        </div>
      ))}
      <div className={cx("pl-abs pl-a5", vis(s === S.compose), s === S.compose && "pl-stamp-in")} style={{ ...at(904, 6), ...d(0.5) }}>
        <b>A5 · Composer</b>
        <span>wraps the whole document into one page</span>
      </div>
      <div className={cx("pl-abs pl-gate", vis(s === S.compose))} style={at(292, 650)}>
        {GATE.map((g, k) => <span key={g} className={cx("tag tag-line", s === S.compose && "pl-pop")} style={d(3.4 + k * 0.3)}>{g}</span>)}
      </div>

      <div className={cx("pl-abs pl-cosmo", vis(s === S.cosmogon))} style={{ left: 26, top: 64, width: 1148, height: 585 }}>
        <CosmogonTop play={s === S.cosmogon} />
      </div>
    </div>
  );
}

function Breakdown({ scene }: { scene: number }) {
  const on = scene === S.breakdown;
  const parts = [
    { key: "typography", note: "wordmark swash · display chunky serif, stacked shadow · accent caps · body sans", viz: <TypeSpec /> },
    { key: "background_layer", note: "wave bands on Pine Ink · treatment: tinted, so only colour and light carry", viz: <Waves w={200} h={88} box="0 330 400 176" /> },
    { key: "content_sections + midground_decor", note: "nav · hero · about · tickets; rainbow U-bends at both edges", viz: <Wireframe /> },
    { key: "centerpiece", note: "sunburst rays behind the h1 in Sunburst Rust and Ray Grey", viz: <SunburstViz /> },
  ];
  return (
    <>
      <svg className={cx("pl-svg", vis(on))} viewBox="0 0 1200 675" aria-hidden="true">
        {parts.map((_, i) => (
          <path key={i} d={`M426 ${ROW(i) + 44} H460`} pathLength={1} className={cx("pl-lead", on && "pl-draw")} style={d(0.5 + i * 1.1)} />
        ))}
      </svg>
      {parts.map((p, i) => (
        <div key={p.key} className={cx("pl-abs pl-part", vis(on), on && "pl-pop")} style={{ ...at(464, ROW(i)), ...d(0.8 + i * 1.1) }}>
          <div className="pl-part-viz">{p.viz}</div>
          <div className="pl-part-txt"><b>{p.key}</b><span>{p.note}</span></div>
        </div>
      ))}
      <div className={cx("pl-abs pl-named", vis(on))} style={at(292, 598)}>
        {PALETTE.map((c, k) => (
          <div key={c.hex} className={cx(on && "pl-pop")} style={d(4.4 + k * 0.12)}>
            <i style={{ background: c.hex }} /><b>{c.name}</b><span>{c.hex}</span>
          </div>
        ))}
      </div>
    </>
  );
}

function NonVlm({ scene }: { scene: number }) {
  const on = scene === S.nonvlm;
  return (
    <>
      <div className={cx("pl-abs pl-nv-title", vis(on), on && "pl-pop")} style={at(480, 104)}>
        <b>Non-VLM pipeline</b>
        <span>words in, words out · no image travels past A1</span>
      </div>
      <svg className={cx("pl-svg", vis(on))} viewBox="0 0 1200 675" aria-hidden="true">
        <path d="M462 330 H1176 M1164 320 L1178 330 L1164 340" pathLength={1} className={cx("pl-rail", on && "pl-draw")} style={d(0.2)} />
      </svg>
      {AGENTS.map((a, k) => (
        <div key={a.id} className={cx("pl-abs pl-station", vis(on), on && "pl-pop is-play")} style={{ ...at(490 + k * 228, 214), ...d(0.5 + k * 1.2) }}>
          <div className={`card-bar bar-${a.bar}`} />
          <div className="pl-st-head"><b>{a.id} · {a.name}</b><span>text-only · {a.does}</span></div>
          <div className="pl-st-viz" style={vars({ "--d0": `${0.9 + k * 1.2}s` })}>
            {k === 0 ? <GridViz /> : k === 1 ? <CopyViz /> : <DecorViz />}
          </div>
        </div>
      ))}
      {on && <i className="pl-doc-token" />}
      <div className={cx("pl-abs pl-label", vis(on), on && "pl-pop")} style={{ ...at(480, 474), ...d(4.6) }}>Code checks the facts</div>
      {CHECKS.map((c, k) => (
        <span key={c} className={cx("pl-abs pl-check", vis(on), on && "pl-stamp-in")}
          style={{ ...at(480 + k * 140, 506), ...vars({ "--rot": `${k % 2 ? 3 : -3}deg` }), ...d(5 + k * 0.35) }}>{c}</span>
      ))}
    </>
  );
}

/* ------------------------------------------------------------------------------------------ small drawings */

function Waves({ h = 558, w = 876, box = "0 0 876 558" }: { h?: number; w?: number; box?: string }) {
  const bands = [DEEP, MARIGOLD, TANGERINE, VERMILION, PINE];
  return (
    <svg viewBox={box} width={w} height={h} preserveAspectRatio="xMidYMid slice" aria-hidden="true" style={{ display: "block", background: PINE }}>
      {bands.map((c, k) => (
        <path key={`b${k}`} d="M-60 470 C 150 380, 300 600, 520 490 S 820 400, 940 460" fill="none" stroke={c} strokeWidth="34" transform={`translate(0 ${k * 30 - 30})`} />
      ))}
      {[MARIGOLD, TANGERINE, VERMILION, DEEP].map((c, k) => (
        <path key={`t${k}`} d="M500 -60 C 620 40, 760 -30, 940 70" fill="none" stroke={c} strokeWidth="30" transform={`translate(0 ${k * 28})`} />
      ))}
    </svg>
  );
}

function sunRays(cx0: number, cy0: number, r: number, n: number) {
  return Array.from({ length: n }, (_, k) => {
    const a0 = (k / n) * Math.PI * 2;
    const a1 = ((k + 0.5) / n) * Math.PI * 2;
    const p = (a: number) => `${(cx0 + Math.cos(a) * r).toFixed(1)},${(cy0 + Math.sin(a) * r).toFixed(1)}`;
    return { k, points: `${cx0},${cy0} ${p(a0)} ${p(a1)}` };
  });
}

function UBend({ side, cy, r0 }: { side: "l" | "r"; cy: number; r0: number }) {
  const colors = [CORAL, TANGERINE, MARIGOLD];
  return (
    <>
      {colors.map((c, k) => {
        const r = r0 - k * 24;
        const d0 = side === "l"
          ? `M -40 ${cy - r} H 70 A ${r} ${r} 0 0 1 70 ${cy + r} H -40`
          : `M 916 ${cy - r} H 806 A ${r} ${r} 0 0 0 806 ${cy + r} H 916`;
        return <path key={c} d={d0} fill="none" stroke={c} strokeWidth="22" />;
      })}
    </>
  );
}

function RetroBackdrop() {
  return <Waves />;
}

function RetroDecor() {
  return (
    <svg viewBox="0 0 876 558" width="876" height="558" aria-hidden="true" style={{ display: "block" }}>
      <g opacity=".26">
        {sunRays(438, 236, 470, 32).map((r) => <polygon key={r.k} points={r.points} fill={r.k % 2 ? GREY : RUST} />)}
      </g>
      <UBend side="l" cy={250} r0={96} />
      <UBend side="r" cy={250} r0={96} />
    </svg>
  );
}

function RetroContent() {
  return (
    <div className="rt">
      <div className="rt-nav">
        <span className="rt-mark">A·76</span>
        <span className="rt-links"><span>Line-up</span><span>Stages</span><span>Vinyl fair</span></span>
        <span className="rt-pill">Buy tickets</span>
      </div>
      <div className="rt-eyebrow">June 18–20 · three days under one sun</div>
      <div className="rt-h1">Analog &rsquo;76</div>
      <p className="rt-sub">Modular synths, warm tape and crate-digging, all weekend long.</p>
      <div className="rt-ctas"><span className="rt-pill">Get passes</span><span className="rt-pill rt-ghost">See the line-up</span></div>
      <div className="rt-about">
        <b>About the fest</b>
        <span>Forty analog acts, two stages and a vinyl fair in the park.</span>
      </div>
    </div>
  );
}

function RetroFore() {
  return (
    <>
      <TapePiece style={{ left: 152, top: 404, rotate: "-8deg" }} />
      <div className="rt-sticker">1976</div>
      <svg className="rt-spark" viewBox="0 0 20 20" style={{ left: 170, top: 150 }} aria-hidden="true"><path d="M10 0 L12 8 L20 10 L12 12 L10 20 L8 12 L0 10 L8 8 Z" fill={LINEN} /></svg>
      <svg className="rt-spark" viewBox="0 0 20 20" style={{ left: 690, top: 300, width: 14, height: 14 }} aria-hidden="true"><path d="M10 0 L12 8 L20 10 L12 12 L10 20 L8 12 L0 10 L8 8 Z" fill={MARIGOLD} /></svg>
    </>
  );
}

function TypeSpec() {
  return (
    <div className="pl-typespec" style={{ background: PINE }}>
      <span className="pl-ts-mark" style={{ color: LINEN, textShadow: `.04em .04em 0 ${MARIGOLD}, .08em .08em 0 ${TANGERINE}, .12em .12em 0 ${VERMILION}` }}>Analog &rsquo;76</span>
      <span className="pl-ts-row" style={{ color: MARIGOLD }}>ACCENT · OSWALD CAPS</span>
      <span className="pl-ts-body" style={{ color: LINEN }}>Body · DM Sans, warm and plain</span>
    </div>
  );
}

function Wireframe() {
  return (
    <svg viewBox="0 0 200 88" width="200" height="88" aria-hidden="true" style={{ display: "block", background: "#F3EFE0" }}>
      {[CORAL, TANGERINE, MARIGOLD].map((c, k) => {
        const r = 22 - k * 6;
        return (
          <Fragment key={c}>
            <path d={`M -4 ${40 - r} H 14 A ${r} ${r} 0 0 1 14 ${40 + r} H -4`} fill="none" stroke={c} strokeWidth="5" />
            <path d={`M 204 ${40 - r} H 186 A ${r} ${r} 0 0 0 186 ${40 + r} H 204`} fill="none" stroke={c} strokeWidth="5" />
          </Fragment>
        );
      })}
      <rect x="46" y="6" width="108" height="6" rx="2" fill={ESPRESSO} opacity=".55" />
      <rect x="160" y="4" width="22" height="9" rx="4.5" fill={VERMILION} />
      <rect x="62" y="18" width="76" height="40" rx="3" fill={ESPRESSO} opacity=".85" />
      <rect x="80" y="64" width="40" height="6" rx="1" fill={ESPRESSO} />
      <rect x="88" y="75" width="24" height="9" rx="4.5" fill={VERMILION} />
    </svg>
  );
}

function SunburstViz() {
  return (
    <svg viewBox="0 0 200 88" width="200" height="88" aria-hidden="true" style={{ display: "block", background: "#F4D9A4" }}>
      {sunRays(100, 44, 130, 24).map((r) => <polygon key={r.k} points={r.points} fill={r.k % 2 ? GREY : RUST} />)}
    </svg>
  );
}

function GridViz() {
  return (
    <svg viewBox="0 0 176 124" width="176" height="124" aria-hidden="true">
      <rect className="pl-v-pop" style={dv(0)} x="10" y="8" width="156" height="12" rx="2" fill="var(--sand)" stroke="var(--ink)" strokeWidth="1.5" />
      <rect className="pl-v-pop" style={dv(0.2)} x="10" y="28" width="156" height="50" rx="2" fill="var(--sand)" stroke="var(--ink)" strokeWidth="1.5" />
      {[0, 1, 2].map((k) => (
        <rect key={k} className="pl-v-pop" style={dv(0.4 + k * 0.12)} x={10 + k * 53} y="86" width="50" height="30" rx="2" fill="var(--sand)" stroke="var(--ink)" strokeWidth="1.5" />
      ))}
      {[36, 62, 88, 114, 140].map((x, k) => (
        <path key={x} className="pl-v-draw" style={dv(0.6 + k * 0.1)} d={`M${x} 2 V122`} pathLength={1} stroke="var(--teal)" strokeWidth="1.5" />
      ))}
    </svg>
  );
}

function CopyViz() {
  return (
    <div className="pl-copyviz">
      <b>Analog &rsquo;76</b>
      {[92, 76, 84, 52].map((w, k) => <i key={k} className="pl-v-grow" style={{ width: `${w}%`, ...dv(0.2 + k * 0.18) }} />)}
      <span className="pl-v-pop" style={dv(1)}>Get passes</span>
    </div>
  );
}

function DecorViz() {
  return (
    <svg viewBox="0 0 176 124" width="176" height="124" aria-hidden="true">
      <g opacity=".5">
        {sunRays(124, 62, 90, 18).map((r) => <polygon key={r.k} className="pl-v-pop" style={dv(1 + r.k * 0.02)} points={r.points} fill={r.k % 2 ? GREY : RUST} />)}
      </g>
      {[CORAL, TANGERINE, MARIGOLD].map((c, k) => {
        const r = 40 - k * 12;
        return <path key={c} className="pl-v-draw" style={dv(0.1 + k * 0.25)} pathLength={1} d={`M -4 ${62 - r} H 40 A ${r} ${r} 0 0 1 40 ${62 + r} H -4`} fill="none" stroke={c} strokeWidth="10" />;
      })}
    </svg>
  );
}

/* --------------------------------------------------------------------------------- the Cosmogon Labs top */

function CosmogonTop({ play }: { play: boolean }) {
  const r = (k: number) => ({ className: cx(play && "pl-rise"), style: d(0.55 + k * 0.2) });
  return (
    <div className="pl-ct">
      <div {...r(0)}>
        <div className="pl-ct-head">
          <span className="pl-ct-brand"><Monogram className="pl-ct-mono" /><span className="wordmark stacked-sm">Cosmogon Labs</span></span>
          <span className="pl-ct-links"><span>Studio</span><span>About</span><span>Evidence</span><span className="btn btn-primary btn-sm">Sign in</span></span>
        </div>
        <Strip />
      </div>
      <div className="pl-ct-hero">
        <div>
          <div {...r(1)}><span className="badge">Welcome to the Studio</span></div>
          <div {...r(2)}><span className="inline-caps pl-ct-what">What should <span className="hl">we</span></span></div>
          <div {...r(3)}>
            <span className="display stacked pl-ct-make" style={{ fontVariationSettings: '"SOFT" 100, "WONK" 1' }}>make?</span>
          </div>
          <p {...r(4)} className={cx("pl-ct-lede", play && "pl-rise")}>
            Name the business and the feeling. Cosmogon Labs routes the feeling to one of 39 aesthetic families,
            reads its references, and composes the page.
          </p>
        </div>
        <div {...r(5)} className={cx("pl-ct-poster", play && "pl-rise")}>
          <Poster name="arch" caption="Plate 01 · Sunset arches" artClassName="pl-ct-art" />
        </div>
      </div>
    </div>
  );
}
