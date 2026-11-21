"use client";
import { useCallback, useEffect, useRef, useState } from "react";

/**
 * A small film clock: scenes of fixed length, each with beats at fractions of the scene. The elapsed time lives in a
 * ref and advances on requestAnimationFrame; React state changes only when the scene or beat changes.
 * `nonce` bumps on every seek so the stage can remount and land on the sought scene without replaying transitions.
 */
export function useTimeline(scenes: { ms: number; beats: { at: number }[] }[], running: boolean) {
  const [scene, setScene] = useState(0);
  const [beat, setBeat] = useState(0);
  const [ended, setEnded] = useState(false);
  const [nonce, setNonce] = useState(0);
  const t = useRef(0);
  const cur = useRef({ scene: 0, beat: 0 });

  useEffect(() => {
    if (!running || ended) return;
    let raf = 0;
    let last = performance.now();
    const tick = (now: number) => {
      t.current += Math.min(100, now - last);
      last = now;
      const s = scenes[cur.current.scene];
      if (t.current >= s.ms) {
        if (cur.current.scene >= scenes.length - 1) {
          t.current = s.ms;
          setEnded(true);
          return;
        }
        t.current = 0;
        cur.current = { scene: cur.current.scene + 1, beat: 0 };
        setScene(cur.current.scene);
        setBeat(0);
      } else {
        const f = t.current / s.ms;
        let b = 0;
        s.beats.forEach((x, k) => { if (x.at <= f) b = k; });
        if (b !== cur.current.beat) {
          cur.current.beat = b;
          setBeat(b);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [running, ended, scenes]);

  const seek = useCallback((k: number, atEnd = false) => {
    const n = Math.max(0, Math.min(scenes.length - 1, k));
    const lastBeat = atEnd ? scenes[n].beats.length - 1 : 0;
    t.current = atEnd ? scenes[n].ms : 0;
    cur.current = { scene: n, beat: lastBeat };
    setBeat(lastBeat);
    setEnded(false);
    setNonce((x) => x + 1);
    if (atEnd || n === 0) {
      setScene(n);
      return;
    }
    // remount on the previous scene's state, then step forward so this scene's own transitions play
    setScene(n - 1);
    requestAnimationFrame(() => requestAnimationFrame(() => {
      if (cur.current.scene === n) setScene(n);
    }));
  }, [scenes]);

  return { scene, beat, ended, nonce, seek };
}

/** Animate a number toward `to` whenever it changes (used by the funnel counters). */
export function useCountUp(to: number, ms = 1600, instant = false) {
  const [v, setV] = useState(instant ? to : 0);
  const from = useRef(instant ? to : 0);
  useEffect(() => {
    if (instant) { from.current = to; setV(to); return; }
    let raf = 0;
    const start = performance.now();
    const a = from.current;
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / ms);
      const e = 1 - Math.pow(1 - p, 3);
      const x = a + (to - a) * e;
      setV(x);
      from.current = x;
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to, ms, instant]);
  return v;
}
