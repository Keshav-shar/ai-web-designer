import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { MAX_PROMPT, Prompt } from "@/lib/prompt";
import { supabaseServer } from "@/lib/supabase/server";

const Body = z.object({ prompt: Prompt });

/** Database refusals -> what the person should do next (never the raw database text). */
function queueError(message: string): { error: string; status: number } {
  if (/quota/i.test(message)) return { error: "You've reached today's limit. Try again tomorrow.", status: 429 };
  if (/already running/i.test(message))
    return { error: "You already have a site in progress. Wait for it, or cancel it first.", status: 409 };
  if (/jobs_prompt_check|char_length/i.test(message))
    return { error: `Keep it between 3 and ${MAX_PROMPT} characters.`, status: 400 };
  if (/profile/i.test(message)) return { error: "Your account isn't fully set up yet. Ask the admin.", status: 403 };
  return { error: "Couldn't queue that request. Please try again.", status: 400 };
}

/**
 * The simple API: authenticate, validate (<= 200 characters, normalized), queue the prompt. The insert runs with the
 * user's own session, so RLS + the quota trigger are the rate limiter; this route holds no privileged key. The PC
 * worker picks the job up, splits the prompt itself (worker/split.py, the only implementation) and writes the split
 * it routed on back to the job.
 */
export async function POST(request: NextRequest) {
  const origin = request.headers.get("origin");
  if (!origin || origin !== request.nextUrl.origin) return NextResponse.json({ error: "bad origin" }, { status: 403 });
  if (!request.headers.get("content-type")?.includes("application/json"))
    return NextResponse.json({ error: "expected JSON" }, { status: 415 });

  const supabase = await supabaseServer();
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "sign in first" }, { status: 401 });

  const parsed = Body.safeParse(await request.json().catch(() => null));
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "Invalid request." }, { status: 400 });
  const prompt = parsed.data.prompt;

  const { data, error } = await supabase.from("jobs").insert({ prompt }).select("id").single();
  if (error) {
    const e = queueError(error.message ?? "");
    return NextResponse.json({ error: e.error }, { status: e.status });
  }
  return NextResponse.json({ job_id: data.id, prompt }, { status: 201 });
}
