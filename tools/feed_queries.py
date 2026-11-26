"""feed_queries.py - submit a list of prompts as real Studio jobs, one at a time (runs ON the engine server).

    /srv/cosmogon/venv/bin/python feed_queries.py QUERIES.json START END --username taste-batch [--out DIR]

Studio allows one active job per account, so each prompt is inserted (prompt only, like the web's /api/generate; the
worker splits it), then followed until it is done or failed (or MAX_WAIT_S), then the next one goes in. Every step is
appended to DIR/manifest.jsonl (default /srv/cosmogon/tmp/batch), so a cycle's jobs can be collected afterwards with
collect_jobs.py. Run it detached: setsid nohup ... > DIR/feed.log 2>&1 &
A file named PAUSE in DIR or its parent holds the next insert (the job in progress finishes): deploy, then remove it.
Uses SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from the worker's .env. Prompts are capped at 200 characters by the
database; a longer one is reported and skipped, never cut.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

WORKER = Path("/srv/cosmogon/studio/worker")
POLL_S, MAX_WAIT_S = 20, 40 * 60


def env():
    for line in (WORKER / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


class Supa:
    def __init__(self):
        self.u = os.environ["SUPABASE_URL"].rstrip("/")
        k = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        self.h = {"apikey": k, **({"Authorization": f"Bearer {k}"} if k.startswith("eyJ") else {})}
        self.c = httpx.Client(timeout=httpx.Timeout(40, connect=15))

    def req(self, method, path, tries=4, **kw):
        for i in range(tries):
            try:
                r = self.c.request(method, self.u + path, headers={**self.h, **kw.pop("headers", {})}, **kw)
                if r.status_code < 500:
                    return r
            except httpx.TransportError:
                pass
            time.sleep(5 * (i + 1))
        raise RuntimeError(f"supabase {method} {path}: retries exhausted")


def log(out: Path, rec: dict):
    rec = {"at": time.strftime("%Y-%m-%d %H:%M:%S"), **rec}
    with (out / "manifest.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(json.dumps(rec, ensure_ascii=False), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries")
    ap.add_argument("start", type=int, help="1-based, inclusive")
    ap.add_argument("end", type=int, help="1-based, inclusive")
    ap.add_argument("--username", required=True)
    ap.add_argument("--out", default="/srv/cosmogon/tmp/batch")
    ap.add_argument("--arm", choices=["deepseek"], help="mark these jobs for the DeepSeek test arm (arms.json)")
    a = ap.parse_args()
    env()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    qs = json.loads(Path(a.queries).read_text(encoding="utf-8"))
    sb = Supa()
    r = sb.req("GET", "/rest/v1/profiles", params={"username": f"eq.{a.username}", "select": "id,daily_quota"})
    rows = r.json() if r.status_code == 200 else []
    if not rows:
        print(f"no Studio account named {a.username!r} (profiles.username)", flush=True)
        return 2
    uid = rows[0]["id"]
    log(out, {"event": "start", "range": [a.start, a.end], "username": a.username, "quota": rows[0]["daily_quota"]})
    def active() -> bool:                                # this account already has a job in the queue / running
        rr = sb.req("GET", "/rest/v1/jobs", params={"user_id": f"eq.{uid}", "status": "not.in.(done,failed)",
                                                     "select": "id"})
        return rr.status_code == 200 and bool(rr.json())

    for n in range(a.start, a.end + 1):
        while active() or (out / "PAUSE").exists() or (out.parent / "PAUSE").exists():   # one at a time; deploys
            time.sleep(15)
        prompt = qs[n - 1]
        if len(prompt) > 200:
            log(out, {"event": "skipped", "n": n, "why": f"{len(prompt)} characters > 200", "prompt": prompt})
            continue
        r = sb.req("POST", "/rest/v1/jobs", tries=1, json={"prompt": prompt, "user_id": uid},
                   headers={"Prefer": "return=representation"})
        if r.status_code >= 300:
            log(out, {"event": "insert failed", "n": n, "status": r.status_code, "body": r.text[:300]})
            if "already running" in r.text:              # someone else's job of this account: wait and retry once
                time.sleep(120)
                r = sb.req("POST", "/rest/v1/jobs", tries=1, json={"prompt": prompt, "user_id": uid},
                           headers={"Prefer": "return=representation"})
            if r.status_code >= 300:
                continue
        job = r.json()[0]
        if a.arm:                                        # read by the worker when the agents start (after routing)
            f = Path("/srv/cosmogon/tmp/batch/arms.json")
            arms = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
            arms[job["id"]] = a.arm
            f.write_text(json.dumps(arms, indent=1), encoding="utf-8")
        log(out, {"event": "queued", "n": n, "job_id": job["id"], "prompt": prompt, "arm": a.arm or "default"})
        t0, status = time.time(), "queued"
        while time.time() - t0 < MAX_WAIT_S:
            time.sleep(POLL_S)
            rr = sb.req("GET", "/rest/v1/jobs", params={"id": f"eq.{job['id']}", "select": "status,error"})
            if rr.status_code == 200 and rr.json():
                status, err = rr.json()[0]["status"], rr.json()[0].get("error")
                if status in ("done", "failed"):
                    log(out, {"event": status, "n": n, "job_id": job["id"], "s": int(time.time() - t0), "error": err})
                    break
        else:
            log(out, {"event": "timeout", "n": n, "job_id": job["id"], "status": status, "s": int(time.time() - t0)})
    log(out, {"event": "finish", "range": [a.start, a.end]})
    return 0


if __name__ == "__main__":
    sys.exit(main())
