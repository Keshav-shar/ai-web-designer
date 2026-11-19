import { NextResponse, type NextRequest } from "next/server";
import { z } from "zod";
import { splitPrompt } from "@/lib/split";
import { supabaseServer } from "@/lib/supabase/server";

const Body = z.object({ prompt: z.string().trim().min(3, "Say a little more").max(300, "Keep it under 300 characters") });

/**
 * The simple API: authenticate, validate, split the prompt into {full_query, vibe_query}, queue the job.
 * The insert runs with the user's own session, so RLS + the quota trigger are the rate limiter; this route
 * holds no privileged key. The PC worker picks the job up from the queue.
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
  if (!parsed.success) return NextResponse.json({ error: parsed.error.issues[0]?.message ?? "invalid prompt" }, { status: 400 });

  const split = await splitPrompt(parsed.data.prompt);
  const { data, error } = await supabase.from("jobs").insert({ prompt: parsed.data.prompt, split }).select("id").single();
  if (error) {
    const msg = error.message || "could not queue the job";
    const status = /quota/.test(msg) ? 429 : /already running/.test(msg) ? 409 : 400;
    return NextResponse.json({ error: msg }, { status });
  }
  return NextResponse.json({ job_id: data.id, split }, { status: 201 });
}
