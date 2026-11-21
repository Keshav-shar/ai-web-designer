import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { MAX_PROMPT, Prompt } from "@/lib/prompt";
import { supabaseServer } from "@/lib/supabase/server";

const Body = z.object({ prompt: Prompt });

// Each step is bounded so a stalled auth or database call becomes a clear error instead of an endless "Queuing…".
const AUTH_MS = 10_000;
const INSERT_MS = 15_000;
export const maxDuration = 30;

/** Database refusals -> what the person should do next (never the raw database text). */
function queueError(message: string, code: string): { error: string; status: number } {
  if (/quota/i.test(message)) return { error: "You've reached today's limit. Try again tomorrow.", status: 429 };
  if (/already running/i.test(message))
    return { error: "You already have a site in progress. Wait for it, or cancel it first.", status: 409 };
  if (/jobs_prompt_check|char_length/i.test(message))
    return { error: `Keep it between 3 and ${MAX_PROMPT} characters.`, status: 400 };
  if (/profile/i.test(message)) return { error: "Your account isn't fully set up yet. Ask the admin.", status: 403 };
  if (code === "55P03" || code === "57014" || /abort|timeout/i.test(message))
    return { error: "The queue didn't answer in time. Please try again in a moment.", status: 503 };
  if (code === "42501") return { error: "The queue refused this request (database permissions). Ask the admin.", status: 403 };
  return { error: "Couldn't queue that request. Please try again.", status: 400 };
}

function within<T>(ms: number, p: Promise<T>): Promise<T> {
  return Promise.race([p, new Promise<T>((_, no) => setTimeout(() => no(new Error(`timeout after ${ms} ms`)), ms))]);
}

/**
 * The simple API: authenticate, validate (<= 200 characters, normalized), queue the prompt. The insert runs with the
 * user's own session, so RLS + the quota trigger are the rate limiter; this route holds no privileged key. The PC
 * worker picks the job up, splits the prompt itself (worker/split.py, the only implementation) and writes the split
 * it routed on back to the job. Failures are logged with their step and timing (Vercel function logs).
 */
export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (!origin || origin !== request.nextUrl.origin) return NextResponse.json({ error: "bad origin" }, { status: 403 });
  if (!request.headers.get("content-type")?.includes("application/json"))
    return NextResponse.json({ error: "expected JSON" }, { status: 415 });

  const t0 = Date.now();
  const supabase = await supabaseServer();
  let user;
  try {
    ({ data: { user } } = await within(AUTH_MS, supabase.auth.getUser()));
  } catch (e) {
    console.error(`[generate] auth step failed after ${Date.now() - t0} ms:`, e);
    return NextResponse.json({ error: "Couldn't check your sign-in in time. Please try again." }, { status: 503 });
  }
  if (!user) return NextResponse.json({ error: "sign in first" }, { status: 401 });

  const parsed = Body.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid request." }, { status: 400 });
  const prompt = parsed.data.prompt;

  const t1 = Date.now();
  const { data, error } = await supabase.from("jobs").insert({ prompt }).select("id")
    .abortSignal(AbortSignal.timeout(INSERT_MS)).single();
  if (error) {
    console.error(`[generate] insert failed after ${Date.now() - t1} ms (auth ${t1 - t0} ms): ${error.code ?? "-"} ${error.message}`);
    const e = queueError(error.message ?? "", error.code ?? "");
    return NextResponse.json({ error: e.error, code: error.code ?? null }, { status: e.status });
  }
  return NextResponse.json({ job_id: data.id, prompt }, { status: 201 });
}
