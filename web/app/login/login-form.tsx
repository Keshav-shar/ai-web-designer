"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { loginId, normalizeUsername } from "@/lib/auth/username";
import { supabaseBrowser } from "@/lib/supabase/client";

const WRONG = "Username or password is incorrect.";

/** Username + password only: accounts are created by the admin and handed out; there is no sign-up here. */
export function LoginForm({ next }: { next: string }) {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const u = normalizeUsername(username);
    if (!u) {
      setError(WRONG); // same message as a wrong password: never reveal which usernames exist
      return;
    }
    setBusy(true);
    const { error } = await supabaseBrowser().auth.signInWithPassword({ email: loginId(u), password });
    if (error) {
      setBusy(false);
      setError(error.status === 429 ? "Too many attempts. Wait a minute and try again." : WRONG);
      return;
    }
    router.replace(next);
    router.refresh();
  }

  return (
    <form onSubmit={submit} className="mt-8 space-y-5">
      <div className="space-y-2">
        <label htmlFor="username" className="title-sm block text-[0.78rem]">Username</label>
        <input
          id="username" name="username" type="text" required autoComplete="username" autoCapitalize="none"
          spellCheck={false} maxLength={24} value={username} onChange={(e) => setUsername(e.target.value)}
          className="field"
        />
      </div>
      <div className="space-y-2">
        <label htmlFor="password" className="title-sm block text-[0.78rem]">Password</label>
        <input
          id="password" name="password" type="password" required autoComplete="current-password" value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="field"
        />
      </div>
      {error && <p role="alert" className="notice">{error}</p>}
      <button className="btn btn-primary w-full" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
    </form>
  );
}
