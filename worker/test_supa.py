"""test_supa.py - the worker's Supabase client under the failures seen in production (no network: httpx.MockTransport).

    D:\\caches\\venvs\\uifp\\Scripts\\python.exe worker\\test_supa.py

Covers: a keep-alive socket reset mid-upload (WinError 10054) is retried; a site insert whose reply was lost is
recognised on retry (unique job_id) instead of failing the job; claim is never retried blindly and a lost claim is
re-queued; a missing grant is caught by preflight without writing anything; 503s back off; DNS failures read as
network errors in the studio's message.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent))
os.environ["SUPABASE_URL"] = "https://example.supabase.co"
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = "sb_secret_test"
import supa  # noqa: E402

FAILS: list[str] = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def client(handler):
    log = []

    def h(req: httpx.Request):
        log.append((req.method, req.url.path, dict(req.url.params), req.content))
        return handler(req, len(log))
    return supa.Supa(transport=httpx.MockTransport(h), sleep=lambda s: None), log


def t_upload_reset():
    def handler(req, n):
        if n == 1:
            raise httpx.ReadError("[WinError 10054] An existing connection was forcibly closed by the remote host")
        return httpx.Response(200, json={"Key": "sites/x"})
    sb, log = client(handler)
    sb.upload("u/j/assets/abc.webp", b"img", "image/webp")
    check(len(log) == 2 and all(m == "POST" for m, *_ in log), "upload: a reset socket is retried and succeeds")


def t_insert_site_lost_reply():
    row = {"job_id": "11111111-1111-1111-1111-111111111111", "user_id": "u", "html_path": "a", "css_path": "b"}

    def handler(req, n):
        if req.method == "POST" and n == 1:
            raise httpx.ReadError("connection reset after the insert committed")
        if req.method == "POST":
            return httpx.Response(409, json={"code": "23505", "message": "duplicate key value violates unique constraint"})
        return httpx.Response(200, json=[{**row, "id": "site-1"}])
    sb, log = client(handler)
    got = sb.insert_site(row)
    check(got["id"] == "site-1" and log[-1][0] == "GET", "insert_site: a lost reply + 409 on retry returns the saved row")


def t_claim_not_retried():
    def handler(req, n):
        if req.url.path.endswith("/rpc/claim_job"):
            raise httpx.ConnectError("[Errno 11001] getaddrinfo failed")
        return httpx.Response(200, json=[{"id": "j1"}])
    sb, log = client(handler)
    try:
        sb.claim("host-1")
        check(False, "claim raises on a network error")
    except httpx.ConnectError as e:
        check(supa.is_network(e), "claim: network error surfaces (and is recognised as one)")
    check(sum(1 for m, p, *_ in log if p.endswith("claim_job")) == 1, "claim: never retried blindly (not idempotent)")
    n = sb.requeue_mine("host-1")
    m, p, params, body = log[-1]
    check(n == 1 and m == "PATCH" and params.get("worker_id") == "eq.host-1" and json.loads(body)["status"] == "queued",
          "requeue_mine: puts back what this worker may have claimed")


def t_preflight_grants():
    def missing(req, n):
        if req.method == "POST" and req.url.path.endswith("/job_events"):
            return httpx.Response(403, json={"code": "42501", "message": "permission denied for table job_events"})
        if req.method == "POST" and req.url.path.endswith("/sites"):
            return httpx.Response(409, json={"code": "23503", "message": "violates foreign key constraint"})
        return httpx.Response(200, json=[])
    sb, log = client(missing)
    probs = sb.preflight("host", beat=False)
    check(any("insert job_events" in p and "20261124000000_service_role_grants.sql" in p for p in probs),
          f"preflight: a missing INSERT grant is reported with the fix ({probs[:1]})")
    check(not any("insert sites" in p for p in probs), "preflight: an FK rejection (409) means the grant exists")
    check(not any(m == "DELETE" for m, *_ in log), "preflight: nothing was written (no clean-up needed)")
    check(not any(p.endswith("/engine_status") and m == "POST" for m, p, *_ in log), "preflight(beat=False): no heartbeat")


def t_backoff_503():
    def handler(req, n):
        return httpx.Response(503, text="busy") if n <= 2 else httpx.Response(200, json=[{"status": "done"}])
    sb, log = client(handler)
    check(sb.job_status("j") == "done" and len(log) == 3, "job_status: 503s back off and recover")


def t_user_message():
    import worker
    msg = worker.user_message(httpx.ReadError("[WinError 10054] forcibly closed"))
    check("lost its connection" in msg, f"studio message for a network failure: {msg!r}")
    msg2 = worker.user_message(RuntimeError("supabase PATCH /rest/v1/jobs: 403 permission denied"))
    check("permissions" in msg2, "studio message for missing grants")


for t in (t_upload_reset, t_insert_site_lost_reply, t_claim_not_retried, t_preflight_grants, t_backoff_503,
          t_user_message):
    t()
print("\nALL PASS" if not FAILS else f"\n{len(FAILS)} FAILED")
sys.exit(1 if FAILS else 0)
