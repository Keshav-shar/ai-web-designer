"use client";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { SiteMockup } from "@/components/site-mockup";
import { TapePiece } from "@/components/cosmos";
import { Card, cx } from "@/components/ui";
import { MAX_PROMPT, normalizePrompt } from "@/lib/prompt";
import { supabaseBrowser } from "@/lib/supabase/client";

type Job = { id: string; prompt: string; status: string };
type Ev = { id: number; stage: string; message: string; data: Record<string, any> | null };
type Site = { id: string; title: string | null };
export type Engine = { state: string; last_seen: string; section_mode?: string | null } | null;

const ONLINE_MS = 2 * 60 * 1000;   // the worker beats every 20 s (own thread); 2 min of silence = offline
const isOnline = (e: Engine) => !!e && e.state !== "offline" && Date.now() - new Date(e.last_seen).getTime() < ONLINE_MS;

/** "Engine online / offline" from the worker's heartbeat row (engine_status), refreshed every 20 s. The worker beats
 *  every 20 s from its own thread, also in the middle of a generation, so the badge holds steady while it works. */
function EngineBadge({ initial }: { initial: Engine }) {
  const [engine, setEngine] = useState<Engine>(initial);
  const [, tick] = useState(0);
  useEffect(() => {
    const sb = supabaseBrowser();
    const load = async () => {
      const { data } = await sb.from("engine_status").select("state, last_seen, section_mode").order("last_seen", { ascending: false }).limit(1).maybeSingle();
      setEngine((data as Engine) ?? null);
      tick((n) => n + 1);
    };
    const t = setInterval(load, 20_000);
    return () => clearInterval(t);
  }, []);
  const on = isOnline(engine);
  return (
    <>
      <p className="meta flex items-center gap-2.5" title={engine ? `last seen ${new Date(engine.last_seen).toLocaleTimeString()}` : "no heartbeat yet"}>
        <span aria-hidden="true" className={cx("inline-block h-2.5 w-2.5 rounded-full", on ? "bg-teal" : "border-2 border-rule bg-cream")} />
        {on ? (engine?.state === "busy" ? "Engine online · working on a request" : "Engine online")
          : "Engine offline · your request waits in the queue until it's back"}
      </p>
      {on && engine?.section_mode === "agents" && (
        <p className="mt-2 max-w-[70ch] text-[0.84rem] text-muted">
          AI pipeline on: your prompt and the engine&rsquo;s reference images are sent to Google Gemini and Gemma&rsquo;s
          free tier, to free models on OpenRouter (Ling, NVIDIA Nemotron) and to Groq; free tiers may log inputs or use
          them for training. Mistral AI&rsquo;s free tier is the last fallback. Don&rsquo;t include private details.
        </p>
      )}
    </>
  );
}

const STATUS: Record<string, string> = {
  queued: "Waiting for the engine. It runs on one machine, so this can take a moment.",
  routing: "Routing the vibe through 39 aesthetic families…",
  recipe: "Reading the family's folders: palette, type, imagery…",
  generating: "Designing the page…",
  assembling: "Assembling the page…",
};
const FAILED_FALLBACK = "The engine couldn't build this one. Try rephrasing it: what it is + how it should feel.";

/** The pipeline's steps as the worker reports them (worker/eta.py); repair / backup page count as the check step. */
const STEPS: [string, string][] = [["route", "Routing"], ["a1", "References"], ["a2", "Layout"], ["a3", "Copy"],
  ["a4", "Decor"], ["a5", "Compose"], ["check", "Check"], ["publish", "Preview"]];
const stepIndex = (s?: string) => s === "repair" || s === "fallback" ? 6 : Math.max(0, STEPS.findIndex(([k]) => k === s));

function timeLeft(s: number): string {
  if (s <= 1) return "Finishing up";
  if (s < 45) return "Under a minute left";
  if (s < 90) return "About a minute left";
  return `About ${Math.round(s / 60)} min left`;
}
const clock = (s: number) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, "0")}`;

/** Live progress: the step track, the latest pipeline line, the expected time left (counted down between events). */
function Progress({ events, recv, title, onCancel, cancelling }: {
  events: Ev[]; recv: Map<number, number>; title: string; onCancel: () => void; cancelling: boolean;
}) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const timed = [...events].reverse().find((e) => typeof e.data?.eta_s === "number");
  const since = timed ? (now - (recv.get(timed.id) ?? now)) / 1000 : 0;
  const left = timed ? Math.max(0, timed.data!.eta_s - since) : null;
  const elapsed = timed ? timed.data!.elapsed_s + since : null;
  const cur = stepIndex(timed?.data?.step);
  const lines = events.filter((e) => e.data?.ui).map((e) => e.message);
  const recent = lines.slice(-4, -1).reverse();
  return (
    <Card bar="gold" className="overflow-hidden">
      <div className="space-y-4 px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="font-ui text-[0.95rem] font-semibold uppercase tracking-[0.12em] text-ink">{title}</p>
            {left !== null && (
              <p className="meta mt-1">{timeLeft(left)} · {clock(elapsed ?? 0)} elapsed</p>
            )}
          </div>
          <button type="button" onClick={onCancel} disabled={cancelling} className="btn btn-ghost btn-sm shrink-0">
            {cancelling ? "Cancelling…" : "Cancel"}
          </button>
        </div>
        {timed && (
          <ol className="grid grid-cols-8 gap-1.5" aria-label="Pipeline steps">
            {STEPS.map(([k, label], i) => (
              <li key={k} className="min-w-0" aria-current={i === cur ? "step" : undefined}>
                <span className={cx("block h-1.5 rounded-full", i < cur ? "bg-teal" : i === cur ? "bg-gold" : "bg-line")} />
                <span className={cx("mt-1 hidden truncate text-[0.72rem] sm:block", i === cur ? "font-semibold text-ink" : "text-muted")}>
                  {label}
                </span>
              </li>
            ))}
          </ol>
        )}
        {recent.length > 0 && (
          <ul className="space-y-0.5 text-[0.84rem] text-muted">
            {recent.map((m, i) => <li key={i} className="truncate">{m}</li>)}
          </ul>
        )}
      </div>
      <div className="shimmer h-1" />
    </Card>
  );
}

/** The studio: one prompt in (<= 200 characters), the generated website shown inline as a mockup. */
export function Studio({ signedIn, initialJob, latest, engine }: { signedIn: boolean; initialJob: Job | null; latest: Site | null; engine: Engine }) {
  const [prompt, setPrompt] = useState("");
  const [job, setJob] = useState<Job | null>(initialJob);
  const [jobStatus, setJobStatus] = useState<string | null>(initialJob?.status ?? null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const seen = useRef(new Set<number>());
  const recv = useRef(new Map<number, number>());   // when each event reached this browser (drives the countdown)

  const add = useCallback((list: Ev[], loaded = false) => {
    const fresh = list.filter((e) => !seen.current.has(e.id));
    const t = Date.now();
    fresh.forEach((e) => {
      seen.current.add(e.id);
      // live events: now; events loaded after a reload: the server's own time (never in the future)
      recv.current.set(e.id, loaded && typeof e.data?.at === "number" ? Math.min(t, e.data.at) : t);
    });
    if (fresh.length) setEvents((prev) => [...prev, ...fresh].sort((a, b) => a.id - b.id));
  }, []);

  // Live progress: job_events INSERTs + the job row's own status (so a failure without an event still ends the wait).
  useEffect(() => {
    if (!job) return;
    const sb = supabaseBrowser();
    seen.current = new Set();
    setEvents([]);
    const ch = sb
      .channel(`job-${job.id}`)
      .on("postgres_changes", { event: "INSERT", schema: "public", table: "job_events", filter: `job_id=eq.${job.id}` },
        (p) => add([p.new as Ev]))
      .on("postgres_changes", { event: "UPDATE", schema: "public", table: "jobs", filter: `id=eq.${job.id}` },
        (p) => setJobStatus((p.new as { status?: string }).status ?? null))
      .subscribe(async (status) => {
        if (status === "SUBSCRIBED") {
          const [{ data: evs }, { data: row }] = await Promise.all([
            sb.from("job_events").select("id, stage, message, data").eq("job_id", job.id).order("id"),
            sb.from("jobs").select("status").eq("id", job.id).maybeSingle(),
          ]);
          add((evs as Ev[]) ?? [], true);
          if (row?.status) setJobStatus(row.status);
        }
      });
    return () => { sb.removeChannel(ch); };
  }, [job, add]);

  const done = events.find((e) => e.stage === "done");
  const failedEv = events.find((e) => e.stage === "failed");
  const failed = failedEv ? failedEv.message : jobStatus === "failed" ? FAILED_FALLBACK : null;
  const last = [...events].reverse().find((e) => e.stage in STATUS);
  const sec = useMemo(() => [...events].reverse().find((e) => e.stage === "generating" && e.data?.n), [events]);
  const running = !!job && !done && !failed;
  const uiLine = useMemo(() => [...events].reverse().find((e) => e.data?.ui), [events]);
  const status = !running ? null
    : last?.stage === "generating" && sec ? `Composing sections (${sec.data!.i + 1}/${sec.data!.n})…`
    : uiLine && last && last.stage !== "routing" && last.stage !== "recipe" ? uiLine.message
    : STATUS[last?.stage ?? jobStatus ?? "queued"] ?? STATUS.queued;
  const shown: Site | null = done ? { id: done.data!.site_id, title: job?.prompt ?? null } : !job ? latest : null;

  const clean = normalizePrompt(prompt);
  const letters = (clean.match(/[\p{L}\p{N}]/gu) ?? []).length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (clean.length < 3 || letters < 2) {
      setError("Describe the site in a few words: what it is and how it should feel.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await fetch("/api/generate", {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ prompt: clean }),
        signal: AbortSignal.timeout(40_000),     // the route bounds itself at ~25 s; never leave "Queuing…" spinning
      });
      const j = await r.json().catch(() => ({}));
      if (r.status === 401) throw new Error("signin");
      if (!r.ok) throw new Error(j.error ?? `The studio server answered ${r.status}. Please try again.`);
      setJob({ id: j.job_id, prompt: j.prompt ?? clean, status: "queued" });
      setJobStatus("queued");
    } catch (err) {
      const timedOut = err instanceof DOMException && (err.name === "TimeoutError" || err.name === "AbortError");
      setError(timedOut ? "The studio server didn't answer in 40 s. Please try again."
        : err instanceof TypeError ? "Couldn't reach the studio server. Check your connection and try again."
        : err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!job) return;
    setCancelling(true);
    const { data, error: err } = await supabaseBrowser().rpc("cancel_job", { job: job.id });
    setCancelling(false);
    if (err) setError("Couldn't cancel right now. Please try again.");
    else if (data) setJobStatus("failed");
  }

  return (
    <div className="mx-auto max-w-[62rem] space-y-8">
      <div className="relative">
        <TapePiece style={{ top: -14, left: "50%", marginLeft: -56, transform: "rotate(-3deg)" }} />
        <form onSubmit={submit} className="card relative px-5 pb-5 pt-7 md:px-8 md:pb-7 md:pt-9">
          <label htmlFor="prompt" className="title-sm mb-3 block">Describe the website</label>
          <textarea
            id="prompt" rows={3} maxLength={MAX_PROMPT} required value={prompt} onChange={(e) => setPrompt(e.target.value)}
            disabled={running}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); e.currentTarget.form?.requestSubmit(); } }}
            aria-describedby="prompt-help prompt-count"
            className="field resize-none text-[1.15rem] leading-relaxed"
            placeholder="a natural wine bar in Lisbon, hand-drawn and loud"
          />
          <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
            <p id="prompt-help" className="text-[0.9rem] text-muted">What it is, then how it should feel. Enter to send.</p>
            <div className="flex items-center gap-4">
              <span id="prompt-count" className={cx("meta", prompt.length >= MAX_PROMPT && "text-cta")}>
                {prompt.length}/{MAX_PROMPT}
              </span>
              <button className="btn btn-primary" disabled={busy || running || clean.length < 3}>
                {busy ? "Queuing…" : running ? "Working…" : "Generate"}
              </button>
            </div>
          </div>
        </form>
      </div>

      {signedIn && <EngineBadge initial={engine} />}

      {error === "signin" ? (
        <p role="alert" className="notice">
          <Link className="font-bold underline" href="/login">Sign in</Link> to generate. The studio is invite-only while the engine runs on one machine.
        </p>
      ) : error ? (
        <p role="alert" className="notice">{error}</p>
      ) : null}
      {!signedIn && !error && (
        <p className="text-center text-muted">Invite-only for now. <Link className="font-bold text-cta underline" href="/login">Sign in</Link> to generate.</p>
      )}

      <div aria-live="polite">
        {status && (
          <Progress events={events} recv={recv.current} title={status} onCancel={cancel} cancelling={cancelling} />
        )}
        {failed && <p role="alert" className="notice">{failed === "Cancelled." ? "Cancelled. You can start a new one." : failed}</p>}
      </div>

      {shown && (
        <div className="rise space-y-5 pt-4">
          <div className="flex flex-wrap items-end justify-between gap-4">
            <div>
              <p className="eyebrow">fresh off the press</p>
              <h2 className="title">{shown.title ?? "Your site"}</h2>
            </div>
            <div className="flex flex-wrap gap-3">
              <a className="btn btn-ghost btn-sm" href={`/sites/${shown.id}/preview`} target="_blank" rel="noopener">Open full page</a>
              <a className="btn btn-primary btn-sm" href={`/sites/${shown.id}/download`} download>Download code (.zip)</a>
              <Link className="btn btn-quiet btn-sm" href="/sites">All sites →</Link>
            </div>
          </div>
          <div className="relative">
            <SiteMockup src={`/sites/${shown.id}/preview`} label={shown.title ?? "your site"} />
          </div>
        </div>
      )}
    </div>
  );
}
