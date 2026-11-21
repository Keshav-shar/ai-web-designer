"use client";
import { useEffect, useRef, useState } from "react";
import { cx } from "@/components/ui";

const VIEW = { desktop: { w: 1440, h: 640 }, phone: { w: 390, h: 720 } } as const;

/**
 * The generated website, shown inside the studio as a browser-window mockup. The page renders at its real
 * width (1440 / 390) inside a sandboxed iframe (no scripts, opaque origin) and is scaled to fit.
 */
export function SiteMockup({ src, label, poster }: { src: string; label: string; poster?: string | null }) {
  const [mode, setMode] = useState<keyof typeof VIEW>("desktop");
  const [w, setW] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!box.current) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(box.current);
    return () => ro.disconnect();
  }, []);

  const v = VIEW[mode];
  const scale = w ? Math.min(1, w / v.w) : 0;
  const left = mode === "phone" ? Math.max(0, (w - v.w * scale) / 2) : 0;

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center gap-3 border-b-2 border-ink bg-sand px-4 py-3">
        <span aria-hidden="true" className="flex gap-1.5">
          <i className="h-3 w-3 rounded-full bg-gold" /><i className="h-3 w-3 rounded-full bg-vermilion" /><i className="h-3 w-3 rounded-full bg-teal" />
        </span>
        <span className="min-w-0 flex-1 truncate rounded-full border-2 border-ink bg-cream px-4 py-1 text-center text-[0.8rem] text-muted">
          {label}
        </span>
        <div role="group" aria-label="Viewport" className="flex rounded-full border-2 border-ink bg-cream p-0.5 font-ui text-[0.78rem] font-semibold uppercase tracking-[0.12em]">
          {(Object.keys(VIEW) as (keyof typeof VIEW)[]).map((m) => (
            <button key={m} type="button" onClick={() => { setMode(m); }} aria-pressed={mode === m}
              className={cx("rounded-full px-3 py-1", mode === m ? "bg-forest text-cream" : "text-muted hover:text-ink")}>
              {m}
            </button>
          ))}
        </div>
      </div>
      <div ref={box} className="relative overflow-hidden bg-cream" style={{ height: v.h }}>
        {poster && !loaded && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={poster} alt="" aria-hidden="true" className="absolute inset-0 h-full w-full object-cover object-top opacity-80" />
        )}
        {!loaded && <div className="shimmer absolute inset-x-0 top-0 h-1" />}
        {scale > 0 && (
          <iframe
            key={`${src}-${mode}`}
            title={`Generated website: ${label}`}
            src={src}
            sandbox=""
            loading="lazy"
            onLoad={() => setLoaded(true)}
            className={cx("absolute top-0 border-0 bg-transparent", mode === "phone" && "rounded-[1.5rem] shadow-xl")}
            style={{ left, width: v.w, height: v.h / scale, transform: `scale(${scale})`, transformOrigin: "top left" }}
          />
        )}
      </div>
    </div>
  );
}
