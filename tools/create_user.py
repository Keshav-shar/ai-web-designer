"""create_user.py - create an invited account: a USERNAME + password (no email anywhere in the app).

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe tools\\create_user.py --username ana [--quota 5]
    ... --password "their-password"        # otherwise a strong one is generated and printed ONCE, here only

Usernames: 3-24 characters of a-z 0-9 . _ - (case-insensitive, stored lower-case, unique).
Supabase Auth needs an email-shaped login ID, so the account is created as `<username>@<LOGIN_ID_DOMAIN>`: a
placeholder that is never shown or emailed (the account is created confirmed; sign-ups stay off). The default
domain must match web/lib/auth/username.ts (NEXT_PUBLIC_LOGIN_ID_DOMAIN on Vercel if you change it).
Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY (+ optional LOGIN_ID_DOMAIN) from the environment or worker/.env.
Nothing is written to disk; hand the username and password to the person yourself.
"""
from __future__ import annotations

import argparse
import os
import re
import secrets
import string
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,24}$")


def load_env() -> None:
    p = ROOT / "worker" / ".env"
    if p.exists():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def strong_password(n: int = 20) -> str:
    alphabet = string.ascii_letters + string.digits + "-_.!@#"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(n))
        if any(c.islower() for c in pw) and any(c.isupper() for c in pw) and any(c.isdigit() for c in pw):
            return pw


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--username", required=True)
    ap.add_argument("--password", help="at least 10 characters; omit to generate one")
    ap.add_argument("--quota", type=int, help="sites per 24 h (profiles.daily_quota, default 5)")
    a = ap.parse_args(argv)

    load_env()
    url, key = os.getenv("SUPABASE_URL", "").rstrip("/"), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    domain = os.getenv("LOGIN_ID_DOMAIN", "users.serpman.invalid")
    if not (url and key):
        print("set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (environment or worker/.env)", file=sys.stderr)
        return 2
    username = a.username.strip().lower()
    if not USERNAME_RE.fullmatch(username):
        print("username must be 3-24 characters of a-z 0-9 . _ -", file=sys.stderr)
        return 2
    password = a.password or strong_password()
    if len(password) < 10:
        print("password must be at least 10 characters", file=sys.stderr)
        return 2

    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = httpx.post(f"{url}/auth/v1/admin/users", headers=h, timeout=30,
                   json={"email": f"{username}@{domain}", "password": password, "email_confirm": True,
                         "user_metadata": {"username": username}})
    if r.status_code >= 300:
        body = r.text[:300]
        print(f"could not create '{username}': {r.status_code} {body}", file=sys.stderr)
        if "already" in body.lower() or r.status_code == 422 and "registered" in body.lower():
            print("that username is taken", file=sys.stderr)
        elif "email" in body.lower() and "invalid" in body.lower():
            print(f"Supabase rejected the placeholder domain '{domain}'. Set LOGIN_ID_DOMAIN in worker/.env to a domain "
                  "you control (e.g. users.yourdomain.com) and the same value as NEXT_PUBLIC_LOGIN_ID_DOMAIN in "
                  "Vercel, then redeploy.", file=sys.stderr)
        return 1
    uid = r.json()["id"]
    patch = {"username": username}
    if a.quota is not None:
        patch["daily_quota"] = a.quota
    q = httpx.patch(f"{url}/rest/v1/profiles", params={"id": f"eq.{uid}"}, json=patch,
                    headers={**h, "Prefer": "return=minimal"}, timeout=30)
    if q.status_code >= 300:
        print(f"account created, but updating its profile failed: {q.status_code} {q.text[:200]} "
              "(run supabase/migrations/20261123000000_usernames.sql)", file=sys.stderr)
    print(f"created username '{username}'" + (f", quota {a.quota}/day" if a.quota is not None else ""))
    if not a.password:
        print(f"password (shown once, not stored): {password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
