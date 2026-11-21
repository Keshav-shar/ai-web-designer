"use client";
import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { cx } from "@/components/ui";
import { ACTS, SCENES, TAG_LABEL, type CaptionTag } from "@/content/pipeline";
import { EngineLayer, ServeLayer } from "./scenes";
import { buildTiles } from "./tiles";
import { useTimeline } from "./timeline";

const W = 1200;
const H = 675;
const TONE: Record<CaptionTag, string> = {
  corpus: "tag-line", taste: "tag-gold", agents: "tag-forest", code: "tag-teal", result: "tag-cta",
};
const ROMAN = ["I", "II", "III"];
const pad = (n: number) => String(n).padStart(2, "0");

/**
 * The studio's pipeline film: a fixed 1200×675 stage scaled to its column. It plays when at least 40% of it is in
 * view, pauses when it leaves (or the tab hides), and under reduced motion becomes a still step-through.
 * The stage is decorative (aria-hidden); the transcript below carries every scene in text.
 */
export function PipelineShowcase() {
  const { tiles, cream } = useMemo(buildTiles, []);
  const [rm, setRm] = useState(false);
  const [inView, setInView] = useState(false);
  const [tabHidden, setTabHidden] = useState(false);
  const [userPaused, setUserPaused] = useState(false);
  const running = !rm && inView && !tabHidden && !userPaused;
  const { scene, beat, ended, nonce, seek } = useTimeline(SCENES, running);
  const box = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(0);

  useEffect(() => {
    const q = window.matchMedia("(prefers-reduced-motion: reduce)");
    const forced = new URLSearchParams(window.location.search).get("rm") === "1";
    const apply = () => setRm(forced || q.matches);
    apply();
    q.addEventListener("change", apply);
    return () => q.removeEventListener("change", apply);
  }, []);

  // under reduced motion every scene is shown at its final frame
  useEffect(() => {
    if (rm) seek(0, true);
  }, [rm, seek]);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    const io = new IntersectionObserver(([e]) => {
      if (e.intersectionRatio >= 0.4) setInView(true);
      else if (e.intersectionRatio < 0.1) setInView(false);
    }, { threshold: [0, 0.1, 0.4, 0.7] });
    io.observe(el);
    const vis = () => setTabHidden(document.visibilityState === "hidden");
    document.addEventListener("visibilitychange", vis);
    return () => { ro.disconnect(); io.disconnect(); document.removeEventListener("visibilitychange", vis); };
  }, []);

  const scale = w ? w / W : 0;
  const cur = SCENES[scene];
  const reached = Array.from({ length: scene + 1 }, (_, k) => `at-${k}`).join(" ");
  const lines = cur.beats.map((b, k) => ({ ...b, k })).slice(0, rm ? undefined : beat + 1);
  const shown = rm ? lines : lines.slice(-2);
  const last = SCENES.length - 1;

  const go = (k: number) => { seek(k, rm); setUserPaused(false); };

  return (
    <div className="pl-wrap">
      <div className="card pl-frame">
        <div ref={box} className="pl-box" style={w ? { height: H * scale } : undefined}>
          <div key={nonce} aria-hidden="true"
            className={cx("pl-stage", reached, `cur-${scene}`, rm && "pl-rm", !running && "pl-paused")}
            style={{ transform: `scale(${scale})`, opacity: w ? 1 : 0 }}>
            <EngineLayer scene={scene} rm={rm} tiles={tiles} cream={cream} />
            <ServeLayer scene={scene} rm={rm} />
          </div>
        </div>
      </div>

      <div className="pl-controls">
        <p className="pl-now">
          <span className="meta">Act {ROMAN[cur.act]} · {ACTS[cur.act]}</span>
          <b>{pad(scene + 1)} / {SCENES.length}</b>
          <span className="pl-now-title">{cur.title}</span>
        </p>
        <ol className="pl-rail" aria-label="Scenes">
          {SCENES.map((sc, k) => (
            <li key={sc.id} className={cx(k > 0 && SCENES[k - 1].act !== sc.act && "pl-actgap")}>
              <button type="button" onClick={() => go(k)} title={sc.title}
                aria-label={`Scene ${k + 1}: ${sc.title}`} aria-current={k === scene ? "step" : undefined}
                className={cx("pl-dot", k < scene && "is-past", k === scene && "is-now")}>
                {k + 1}
              </button>
            </li>
          ))}
        </ol>
        <div className="pl-btns">
          {rm ? (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => go(scene - 1)} disabled={scene === 0}>Prev</button>
              <button type="button" className="btn btn-primary btn-sm" onClick={() => go(scene + 1)} disabled={scene === last}>Next</button>
            </>
          ) : ended ? (
            <button type="button" className="btn btn-primary btn-sm" onClick={() => go(0)}>Replay</button>
          ) : (
            <>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => setUserPaused((p) => !p)} aria-pressed={userPaused}>
                {userPaused ? "Play" : "Pause"}
              </button>
              <button type="button" className="btn btn-quiet btn-sm" onClick={() => go(0)}>Restart</button>
            </>
          )}
        </div>
      </div>

      <div className="pl-ticker">
        {shown.map((b, i) => (
          <p key={`${scene}-${b.k}`} className={cx("pl-cap rise", !rm && i < shown.length - 1 && "is-old")}>
            <span className={`tag ${TONE[b.tag]}`}>{TAG_LABEL[b.tag]}</span>
            <span>{b.text}</span>
          </p>
        ))}
      </div>

      {(ended || (rm && scene === last)) && (
        <div className="pl-end rise">
          <span className="title-sm">That&rsquo;s the whole pipeline.</span>
          <Link href="/evidence" className="btn btn-ghost btn-sm">See the measurements →</Link>
          <Link href="/about#how" className="btn btn-quiet btn-sm">How it works →</Link>
        </div>
      )}

      <details className="faq pl-transcript">
        <summary>
          <span className="title-sm">Read the whole pipeline</span>
          <span className="plus title-sm" aria-hidden="true">+</span>
        </summary>
        <ol className="pl-script">
          {SCENES.map((sc) => (
            <li key={sc.id}>
              <b>{sc.title}.</b> {sc.beats.map((b) => b.text).join(" ")}
            </li>
          ))}
        </ol>
      </details>
    </div>
  );
}
