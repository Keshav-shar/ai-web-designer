"""create_user.py - create an invited account (email + password), the alternative to Supabase's "Add user" button.

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe tools\\create_user.py --email someone@example.com [--quota 5]
    ... --password "their-password"        # otherwise a strong one is generated and printed ONCE, here only

Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from the environment or worker/.env (the same as the worker).
The account is confirmed immediately; the on_auth_user_created trigger creates its profile (daily quota 5).
Nothing is written to disk; hand the credentials to the person yourself.
"""
from __future__ import annotations

import argparse
import os
import secrets
import string
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


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
    ap.add_argument("--email", required=True)
    ap.add_argument("--password", help="at least 10 characters; omit to generate one")
    ap.add_argument("--quota", type=int, help="sites per 24 h (profiles.daily_quota, default 5)")
    a = ap.parse_args(argv)

    load_env()
    url, key = os.getenv("SUPABASE_URL", "").rstrip("/"), os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and key):
        print("set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY (environment or worker/.env)", file=sys.stderr)
        return 2
    password = a.password or strong_password()
    if len(password) < 10:
        print("password must be at least 10 characters", file=sys.stderr)
        return 2
    h = {"apikey": key, "Authorization": f"Bearer {key}"}
    r = httpx.post(f"{url}/auth/v1/admin/users", headers=h, timeout=30,
                   json={"email": a.email.strip().lower(), "password": password, "email_confirm": True})
    if r.status_code >= 300:
        print(f"could not create the account: {r.status_code} {r.text[:200]}", file=sys.stderr)
        return 1
    uid = r.json()["id"]
    if a.quota is not None:
        q = httpx.patch(f"{url}/rest/v1/profiles", params={"id": f"eq.{uid}"}, json={"daily_quota": a.quota},
                        headers={**h, "Prefer": "return=minimal"}, timeout=30)
        if q.status_code >= 300:
            print(f"account created, but setting the quota failed: {q.status_code} {q.text[:200]}", file=sys.stderr)
    print(f"created {a.email} (id {uid})" + (f", quota {a.quota}/day" if a.quota is not None else ""))
    if not a.password:
        print(f"password (shown once, not stored): {password}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
