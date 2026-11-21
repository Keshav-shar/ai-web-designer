import { FAMILIES, REFS } from "@/content/pipeline";

/**
 * Deterministic tile layouts for Act I (pool → clusters → cream). Every tile keeps one colour from its family, so the
 * mixed pool visibly sorts itself into families when it clusters. Coordinates are in the 1200×675 stage.
 */

export const TILE = 28;
const STEP = 33; // tile + gap
export const POOL = { x: 372, y: 150, cols: 24, rows: 13 };
export const CLUSTER = { x: 372, y: 135, w: 198, h: 158, cols: 4 };
export const CREAM_PER = 7;
export const ENGINE_AT = { x: 166, y: 321 }; // where tiles pour out of the SERP block

export type Tile = {
  i: number; fam: number; color: string; img?: string; cream: boolean;
  px: number; py: number; cx: number; cy: number; kx: number; ky: number;
  lens: number; pour: number;
};

function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const EXTRA_IMGS = [
  { fam: 1, src: "/about/assets/adc355ed2ce4.webp" },
  { fam: 6, src: "/about/assets/975fb4db6fbf.webp" },
  { fam: 9, src: "/about/assets/6ab87d0557a4.webp" },
  { fam: 3, src: "/about/assets/9944cd9f5cd2.webp" },
];

export function buildTiles(): { tiles: Tile[]; cream: { x: number; y: number; w: number; h: number } } {
  const r = rng(1976);
  const n = POOL.cols * POOL.rows; // 312 tiles, 26 per family

  // pool slots, shuffled so the pool looks mixed
  const slots = Array.from({ length: n }, (_, k) => k);
  for (let k = n - 1; k > 0; k--) {
    const j = Math.floor(r() * (k + 1));
    [slots[k], slots[j]] = [slots[j], slots[k]];
  }

  const creamCols = FAMILIES.length;
  const creamW = creamCols * STEP - (STEP - TILE);
  const creamH = CREAM_PER * STEP - (STEP - TILE);
  const creamX = POOL.x + (POOL.cols * STEP - (STEP - TILE) - creamW) / 2;
  const creamY = CLUSTER.y + (3 * CLUSTER.h - creamH) / 2 - 20;

  const tiles: Tile[] = [];
  for (let i = 0; i < n; i++) {
    const fam = i % FAMILIES.length;
    const k = Math.floor(i / FAMILIES.length); // index inside the family
    const colors = FAMILIES[fam].colors;
    const slot = slots[i];
    const px = POOL.x + (slot % POOL.cols) * STEP;
    const py = POOL.y + Math.floor(slot / POOL.cols) * STEP;
    const cellX = CLUSTER.x + (fam % CLUSTER.cols) * CLUSTER.w;
    const cellY = CLUSTER.y + Math.floor(fam / CLUSTER.cols) * CLUSTER.h;
    const cx = cellX + 14 + (k % 7) * 25 + (r() - 0.5) * 5;
    const cy = cellY + 40 + Math.floor(k / 7) * 25 + (r() - 0.5) * 5;
    const cream = k < CREAM_PER;
    let img: string | undefined;
    if (fam === 0 && k < REFS.length) img = REFS[k].src;
    const extra = EXTRA_IMGS.find((e) => e.fam === fam);
    if (extra && k === 1) img = extra.src;
    tiles.push({
      i, fam, color: colors[(k + fam) % colors.length], img, cream,
      px, py, cx, cy,
      kx: creamX + fam * STEP, ky: creamY + (k % CREAM_PER) * STEP,
      lens: (cx - CLUSTER.x) / (CLUSTER.cols * CLUSTER.w),
      pour: Math.round(r() * 900),
    });
  }
  return { tiles, cream: { x: creamX, y: creamY, w: creamW, h: creamH } };
}
