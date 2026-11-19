"use client";
import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";

export function LoginForm({ next }: { next: string }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "sending" | "sent" | "error">("idle");
  const [msg, setMsg] = useState("");
  const redirect = () => `${window.location.origin}/auth/callback?next=${encodeURIComponent(next)}`;

  async function magic(e: React.FormEvent) {
    e.preventDefault();
    setState("sending");
    // shouldCreateUser: false -> only invited accounts get a link (sign-ups are also disabled server-side)
    const { error } = await supabaseBrowser().auth.signInWithOtp({ email, options: { emailRedirectTo: redirect(), shouldCreateUser: false } });
    if (error) {
      setState("error");
      setMsg("That email has no invite, or too many links were requested. Try again in a minute.");
    } else {
      setState("sent");
    }
  }

  async function github() {
    await supabaseBrowser().auth.signInWithOAuth({ provider: "github", options: { redirectTo: redirect() } });
  }

  if (state === "sent") return <p className="mt-8 text-ink">Check your inbox. The link signs you in on this device.</p>;
  return (
    <div className="mt-8 space-y-4">
      <form onSubmit={magic} className="space-y-3">
        <label htmlFor="email" className="eyebrow block">email</label>
        <input
          id="email" type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-2xl border border-line bg-surface/60 px-4 py-3 text-ink placeholder:text-muted"
          placeholder="you@studio.com"
        />
        <button className="btn btn-primary w-full" disabled={state === "sending"}>
          {state === "sending" ? "Sending…" : "Email me a sign-in link"}
        </button>
      </form>
      {state === "error" && <p role="alert" className="text-ink">{msg}</p>}
      <div className="flex items-center gap-3 text-muted"><span className="h-px flex-1 bg-line" />or<span className="h-px flex-1 bg-line" /></div>
      <button type="button" onClick={github} className="btn btn-ghost w-full">Continue with GitHub</button>
    </div>
  );
}
