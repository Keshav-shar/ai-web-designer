"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SiteMockup } from "@/components/site-mockup";
import { supabaseBrowser } from "@/lib/supabase/client";

type Job = { id: string; prompt: string; status: string };
type Ev = { id: number; stage: string; message: string; data: Record<string, any> | null };
type Site = { id: string; title: string | null };

const STATUS: Record<string, string> = {
  queued: "Waiting for the engine. It runs on one machine, so this can take a moment.",
  routing: "Routing the vibe through 39 aesthetic families…",
  recipe: "Reading the family's folders: palette, type, imagery…",
  generating: "Composing sections…",
  assembling: "Assembling the page…",
};

/** Minimal studio: one prompt in, the generated website shown inline as a mockup. */
export function Studio({ signedIn, initialJob, latest }: { signedIn: boolean; initialJob: Job | null; latest: Site | null }) {
  const [prompt, setPrompt] = useState("");
  const [job, setJob] = useState<Job | null>(initialJob);
  const [events, setEvents] = useState<Ev[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const seen = useRef(new Set<number>());

  const add = useCallback((list: Ev[]) => {
    const fresh = list.filter((e) => !seen.current.has(e.id));
    fresh.forEach((e) => seen.current.add(e.id));
    if (fresh.length) setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.id - b.id));
  }, []);

  useEffect(() => {
    if (!job) return;
    const sb = supabaseBrowser();
    seen.current = new Set();
    setEvents([]);
    const ch = sb
      .channel(`job-${job.id}`)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "job_events", filter: `job_id=eq.${job.id}` },
        (p) => add([p.new as Ev]))
      .subscribe(async (status) => {
        if (status === "SUBSCRIBED") {
          const { data } = await sb.from("job_events").select("id, stage, message, data").eq("job_id", job.id).order("id");
          add((data as Ev[]) ?? []);
        }
      });
    return () => { sb.removeChannel(ch); };
  }, [job, add]);

  const done = events.find((e) => e.stage === "done");
  const failed = events.find((e) => e.stage === "failed");
  const last = [...events].reverse().find((e) => e.stage in STATUS);
  const sec = useMemo(() => [...events].reverse().find((e) => e.stage === "generating" && e.data?.n), [events]);
  const running = !!job && !done && !failed;
  const status = !job ? null : failed ? null : done ? null
    : last?.stage === "generating" && sec ? `Composing sections (${sec.data!.i + 1}/${sec.data!.n})…` : STATUS[last?.stage ?? "queued"];
  const shown: Site | null = done ? { id: done.data!.site_id, title: job?.prompt ?? null } : !job ? latest : null;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/generate", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt }) });
      const j = await r.json().catch(() => ({}));
      if (r.status === 401) throw new Error("signin");
      if (!r.ok) throw new Error(j.error ?? "Something went wrong.");
      setJob({ id: j.job_id, prompt, status: "queued" });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-10 space-y-8">
      <form onSubmit={submit} className="glass flex flex-col gap-4 p-4 md:flex-row md:items-end md:p-5">
        <label htmlFor="prompt" className="sr-only">Describe the website</label>
        <textarea
          id="prompt" rows={2} maxLength={300} required value={prompt} onChange={(e) => setPrompt(e.target.value)}
          disabled={running}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }}
          className="min-h-[3.5rem] flex-1 resize-none rounded-2xl border border-line bg-surface/60 px-4 py-3 text-step-2 text-ink placeholder:text-muted"
          placeholder="a natural wine bar in Lisbon, hand-drawn and loud"
        />
        <button className="btn btn-primary md:mb-1" disabled={busy || running || prompt.trim().length < 3}>
          {busy ? "Queuing…" : running ? "Working…" : "Generate"}
        </button>
      </form>

      {error === "signin" ? (
        <p role="alert" className="text-ink">
          <Link className="underline" href="/login">Sign in</Link> to generate. The studio is invite-only while the engine runs on one machine.
        </p>
      ) : error ? (
        <p role="alert" className="glass px-5 py-3 text-ink">{error}</p>
      ) : null}
      {!signedIn && !error && <p className="text-muted">Invite-only for now. <Link className="underline" href="/login">Sign in</Link> to generate.</p>}

      <div aria-live="polite">
        {status && (
          <div className="glass space-y-3 px-5 py-4">
            <p className="text-ink">{status}</p>
            <div className="shimmer h-1 rounded-full" />
          </div>
        )}
        {failed && <p role="alert" className="glass px-5 py-3 text-ink">The run failed: {failed.message}</p>}
      </div>

      {shown && (
        <div className="space-y-4 fade-up">
          <SiteMockup src={`/sites/${shown.id}/preview`} label={shown.title ?? "your site"} />
          <div className="flex flex-wrap gap-3">
            <a className="btn btn-ghost" href={`/sites/${shown.id}/preview`} target="_blank" rel="noopener">Open full page</a>
            <a className="btn btn-ghost" href={`/sites/${shown.id}/download`}>Download .zip</a>
            <Link className="btn btn-ghost" href="/sites">All sites</Link>
          </div>
        </div>
      )}
    </div>
  );
}
