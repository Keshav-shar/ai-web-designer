"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chip, FontSpecimen, GlassCard, SwatchRow, cx } from "@/components/ui";
import { supabaseBrowser } from "@/lib/supabase/client";

type Split = { full_query: string; vibe_query: string; category_hint?: string | null; brand_name?: string | null; source: string };
type Job = { id: string; prompt: string; split: Split; status: string };
type Ev = { id: number; stage: string; message: string; data: Record<string, any> | null; ts: string };

const STAGES = ["routing", "recipe", "generating", "assembling", "done"] as const;
const LABEL: Record<string, string> = { routing: "Routing the vibe", recipe: "Recipe", generating: "Writing sections", assembling: "Assembling", done: "Ready" };

export function Studio({ userId, initialJob }: { userId: string; initialJob: Job | null }) {
  const [prompt, setPrompt] = useState("");
  const [job, setJob] = useState<Job | null>(initialJob);
  const [events, setEvents] = useState<Ev[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [thumbs, setThumbs] = useState<Record<string, string>>({});
  const seen = useRef(new Set<number>());

  const add = useCallback((list: Ev[]) => {
    const fresh = list.filter((e) => !seen.current.has(e.id));
    fresh.forEach((e) => seen.current.add(e.id));
    if (fresh.length) setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.id - b.id));
  }, []);

  // live timeline: Realtime INSERTs on job_events (RLS: own rows only) + one catch-up fetch
  useEffect(() => {
    if (!job) return;
    const sb = supabaseBrowser();
    seen.current = new Set();
    setEvents([]);
    setThumbs({});
    const ch = sb
      .channel(`job-${job.id}`)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "job_events", filter: `job_id=eq.${job.id}` },
        (p) => add([p.new as Ev]))
      .subscribe(async (status) => {
        if (status === "SUBSCRIBED") {
          const { data } = await sb.from("job_events").select("id, stage, message, data, ts").eq("job_id", job.id).order("id");
          add((data as Ev[]) ?? []);
        }
      });
    return () => { sb.removeChannel(ch); };
  }, [job, add]);

  const recipe = useMemo(() => events.find((e) => e.stage === "recipe" && e.data?.palette)?.data ?? null, [events]);
  const uploaded = events.some((e) => e.data?.assets_uploaded);
  const done = events.find((e) => e.stage === "done");
  const failed = events.find((e) => e.stage === "failed");
  const sections = events.filter((e) => e.stage === "generating" && e.data?.id);
  const stage = failed ? "failed" : done ? "done" : [...events].reverse().find((e) => STAGES.includes(e.stage as any))?.stage ?? "queued";

  // reference thumbnails: signed URLs for the user's own folder, once the worker has uploaded them
  useEffect(() => {
    if (!job || !uploaded || !recipe?.assets) return;
    const paths: string[] = recipe.assets.map((a: { path: string }) => `${userId}/${job.id}/${a.path}`);
    supabaseBrowser().storage.from("sites").createSignedUrls(paths, 3600).then(({ data }) => {
      const m: Record<string, string> = {};
      (data ?? []).forEach((s) => { if (s.signedUrl && s.path) m[s.path.split("/").slice(2).join("/")] = s.signedUrl; });
      setThumbs(m);
    });
  }, [job, uploaded, recipe, userId]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error ?? "something went wrong");
      setJob({ id: j.job_id, prompt, split: j.split, status: "queued" });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const running = job && !done && !failed;
  return (
    <div className="mt-10 grid gap-8 lg:grid-cols-[1fr_1.1fr]">
      <div className="space-y-6">
        <GlassCard>
          <form onSubmit={submit} className="space-y-4">
            <label htmlFor="prompt" className="eyebrow block">your site, in one sentence</label>
            <textarea
              id="prompt" rows={4} maxLength={300} required value={prompt} onChange={(e) => setPrompt(e.target.value)}
              disabled={!!running}
              className="w-full resize-none rounded-2xl border border-line bg-surface/60 px-4 py-3 text-step-2 text-ink placeholder:text-muted"
              placeholder="a skincare brand called Dew that feels vintage apothecary, with ingredients and a shop"
            />
            <div className="flex items-center justify-between gap-4">
              <span className="text-[13px] text-muted">{prompt.length}/300</span>
              <button className="btn btn-primary" disabled={busy || !!running || prompt.trim().length < 3}>
                {busy ? "Queuing…" : running ? "Working…" : "Make it"}
              </button>
            </div>
            {error && <p role="alert" className="rounded-2xl border border-line bg-surface px-4 py-3 text-ink">{error}</p>}
          </form>
        </GlassCard>

        {job && (
          <GlassCard>
            <p className="eyebrow">split</p>
            <dl className="mt-3 grid gap-3 text-[15px]">
              <div><dt className="text-muted">full query (what it is)</dt><dd className="text-ink">{job.split.full_query}</dd></div>
              <div><dt className="text-muted">vibe query (how it feels)</dt><dd className="display font-heading text-step-3 text-ink">{job.split.vibe_query}</dd></div>
            </dl>
            <div className="mt-4 flex flex-wrap gap-2">
              {job.split.category_hint && <Chip>{job.split.category_hint}</Chip>}
              {job.split.brand_name && <Chip>{job.split.brand_name}</Chip>}
              <Chip>{job.split.source === "qwen" ? "split by Qwen" : "rule-based split"}</Chip>
            </div>
          </GlassCard>
        )}
      </div>

      <div className="space-y-6" aria-live="polite">
        {job && (
          <GlassCard>
            <ol className="flex flex-wrap gap-2">
              {STAGES.map((s) => {
                const i = STAGES.indexOf(s), cur = STAGES.indexOf(stage as any);
                return (
                  <li key={s}>
                    <Chip tone={s === stage ? "accent" : i < cur || stage === "done" ? "warn" : "plain"}>{LABEL[s]}</Chip>
                  </li>
                );
              })}
            </ol>
            {stage === "queued" && <p className="mt-4 text-muted">Waiting for the engine. It runs on one machine, so it may take a moment to pick this up.</p>}
            {running && <div className="shimmer mt-5 h-1.5 rounded-full" />}
            {failed && <p role="alert" className="mt-4 text-ink">The run failed: {failed.message}</p>}
            {done && (
              <div className="mt-5 flex flex-wrap items-center gap-4">
                <Link className="btn btn-primary" href={`/sites/${done.data?.site_id}`}>Open the site</Link>
                {done.data?.fallback ? <span className="text-muted">{done.data.fallback} section(s) used the plain template</span> : null}
              </div>
            )}
          </GlassCard>
        )}

        {recipe && (
          <GlassCard className="space-y-6 fade-up">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 className="display font-heading text-step-5">{recipe.family}</h2>
              {recipe.taste?.niche && <Chip tone="accent">{recipe.taste.niche}</Chip>}
            </div>
            <SwatchRow colors={recipe.palette} />
            <div className="grid grid-cols-2 gap-6">
              <FontSpecimen role="heading" family={recipe.fonts[0]} css={`https://fonts.googleapis.com/css2?family=${recipe.fonts[0].replaceAll(" ", "+")}&display=swap`} />
              <FontSpecimen role="body" family={recipe.fonts[1]} css={`https://fonts.googleapis.com/css2?family=${recipe.fonts[1].replaceAll(" ", "+")}&display=swap`} />
            </div>
            {recipe.taste?.avoid?.length > 0 && <p className="text-[14px] text-muted">Steering away from: {recipe.taste.avoid.slice(0, 4).join(", ")}</p>}
            {Object.keys(thumbs).length > 0 && (
              <ul className="grid grid-cols-3 gap-3">
                {recipe.assets.map((a: { path: string; role: string; type: string | null }) => thumbs[a.path] && (
                  <li key={a.path} className="overflow-hidden rounded-2xl border border-line">
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img src={thumbs[a.path]} alt={`${a.role} reference (${a.type ?? "image"})`} className="aspect-square w-full object-cover" />
                    <p className="px-2 py-1 text-[12px] text-muted">{a.role}</p>
                  </li>
                ))}
              </ul>
            )}
            {sections.length > 0 && (
              <ul className="flex flex-wrap gap-2">
                {sections.map((s) => <li key={s.id}><Chip tone={s.data?.fallback ? "warn" : "plain"}>{s.data?.id}{s.data?.fallback ? " · template" : ""}</Chip></li>)}
              </ul>
            )}
          </GlassCard>
        )}

        {job && (
          <details className="glass p-6">
            <summary className="cursor-pointer text-muted">Engine log ({events.length})</summary>
            <ol className={cx("mt-4 space-y-1 font-mono text-[12px] text-muted")}>
              {events.map((e) => <li key={e.id}><span className="text-ink">{e.stage}</span> {e.message}</li>)}
            </ol>
          </details>
        )}
      </div>
    </div>
  );
}
