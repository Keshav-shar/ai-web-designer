/**
 * Username + password accounts on top of Supabase Auth.
 *
 * Supabase's password login needs an email-shaped identifier, so each username maps to a fixed placeholder login
 * ID `<username>@<LOGIN_ID_DOMAIN>`. It is never shown, never emailed (accounts are created already confirmed and
 * sign-ups are off) and is not a real mailbox. Keep the domain identical in tools/create_user.py (LOGIN_ID_DOMAIN).
 */
export const USERNAME_RE = /^[a-z0-9._-]{3,24}$/;
export const LOGIN_ID_DOMAIN = process.env.NEXT_PUBLIC_LOGIN_ID_DOMAIN || "users.serpman.invalid";

/** Trimmed, lower-cased username, or null when it can't be one (3-24 of a-z 0-9 . _ -). */
export function normalizeUsername(raw: string): string | null {
  const u = raw.trim().toLowerCase();
  return USERNAME_RE.test(u) ? u : null;
}

export function loginId(username: string): string {
  return `${username}@${LOGIN_ID_DOMAIN}`;
}

/** Display name for a signed-in user: the username from metadata, else the login ID's local part. */
export function usernameOf(user: { user_metadata?: Record<string, unknown> | null; email?: string | null } | null): string | null {
  if (!user) return null;
  const meta = user.user_metadata?.username;
  if (typeof meta === "string" && USERNAME_RE.test(meta)) return meta;
  const local = (user.email ?? "").split("@")[0];
  return USERNAME_RE.test(local) ? local : null;
}
