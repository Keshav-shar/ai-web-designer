"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { supabaseBrowser } from "@/lib/supabase/client";

/** Email + password only: accounts are created by the admin and handed out; there is no sign-up here. */
export function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const { error } = await supabaseBrowser().auth.signInWithPassword({ email: email.trim(), password });
    if (error) {
      setBusy(false);
      // one message for every failure: never reveal whether an email has an account
      setError(error.status === 429 ? "Too many attempts. Wait a minute and try again." : "Email or password is incorrect.");
      return;
    }
    router.replace(next);
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="mt-8 space-y-4">
      <div className="space-y-2">
        <label htmlFor="email" className="eyebrow block" style={{ marginBottom: 0 }}>email</label>
        <input
          id="email" type="email" required autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)}
          className="w-full rounded-2xl border border-line bg-surface/60 px-4 py-3 text-ink placeholder:text-muted"
          placeholder="you@studio.com"
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="password" className="eyebrow block" style={{ marginBottom: 0 }}>password</label>
        <input
          id="password" type="password" required autoComplete="current-password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full rounded-2xl border border-line bg-surface/60 px-4 py-3 text-ink"
        />
      </div>
      {error && <p role="alert" className="text-ink">{error}</p>}
      <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
  );
}
