"""supa.py - the few Supabase calls the worker makes, over plain REST (PostgREST + Storage) with httpx.

Env only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY. The service-role key stays on this PC; the web app never has it.

Write policy: progress writes (job_events, stage status) only drive the studio UI, so a failure is logged and the
job goes on; result writes (uploads, the sites row, `done`) are strict. Status updates never touch a job that is
already done or failed, so a job the user cancelled is not revived.

Network policy: transient failures (DNS hiccups, a keep-alive socket Supabase already closed -> WinError 10054,
502/503/504) are retried with backoff for every idempotent call (GETs, PATCH by id, upserting uploads, the
heartbeat); a site insert that turns out to have gone through (unique job_id) returns the saved row; claim_job is
never retried blindly (it is not idempotent): after a failed claim the worker re-queues anything it may have
claimed (requeue_mine). Idle sockets expire after 20 s so a long engine step doesn't leave a dead one in the pool.
"""
from __future__ import annotations

import os
import threading
import time
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

TABLES = ("jobs", "sites", "job_events", "profiles", "engine_status")
ACTIVE = "(routing,recipe,generating,assembling)"
OPEN = "not.in.(done,failed)"
NIL = "00000000-0000-0000-0000-000000000000"
BACKOFF = (1, 3, 7)
GRANTS_FIX = "run supabase/migrations/20261124000000_service_role_grants.sql in the Supabase SQL editor"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def explain(status: int, body: str, what: str) -> str:
    """Turn a Supabase error into the fix the operator needs."""
    b = body.lower()
    if status == 401 or "invalid api key" in b or "no_authorization" in b:
        return f"{what}: the key was refused - SUPABASE_SERVICE_ROLE_KEY must be the secret key (sb_secret_...)"
    if status == 403 or "42501" in b or "permission denied" in b:
        return f"{what}: permission denied - {GRANTS_FIX}"
    if status == 404 or "pgrst205" in b or "not found" in b:
        return f"{what}: not found - run the supabase/migrations/*.sql files in order"
    return f"{what}: HTTP {status} {body[:160]}"


def is_network(e: BaseException) -> bool:
    return isinstance(e, httpx.TransportError) or "getaddrinfo" in str(e) or "10054" in str(e)


class Supa:
    def __init__(self, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not (self.url and key):
            raise RuntimeError("set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the worker's environment")
        if key.startswith("sb_publishable_"):
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY holds the publishable key; use the secret key (sb_secret_...)")
        # new sb_secret_ keys are not JWTs: send them only as `apikey`; legacy service_role JWTs also go in Authorization
        self.h = {"apikey": key, **({"Authorization": f"Bearer {key}"} if key.startswith("eyJ") else {})}
        self.http = httpx.Client(timeout=httpx.Timeout(60, connect=15), transport=transport,
                                 limits=httpx.Limits(keepalive_expiry=20))
        self.sleep = sleep
        self._transport = transport
        self._beat_warned = False

    def _ok(self, r: httpx.Response) -> httpx.Response:
        if r.status_code >= 300:
            raise RuntimeError(f"supabase {r.request.method} {r.request.url.path}: {r.status_code} {r.text[:300]}")
        return r

    def _send(self, method: str, path: str, *, what: str, tries: int = 4, **kw) -> httpx.Response:
        """One request, retried on transient network errors and 502/503/504 (only call this for idempotent work
        unless tries=1)."""
        for attempt in range(tries):
            try:
                r = self.http.request(method, f"{self.url}{path}", **kw)
            except httpx.TransportError as e:
                if attempt < tries - 1:
                    print(f"warning: supabase {what} retry {attempt + 1}/{tries - 1} ({type(e).__name__}: "
                          f"{str(e)[:90]})", flush=True)
                    self.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
                    continue
                raise
            if r.status_code in (502, 503, 504) and attempt < tries - 1:
                print(f"warning: supabase {what} retry {attempt + 1}/{tries - 1} (HTTP {r.status_code})", flush=True)
                self.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
                continue
            return r
        raise RuntimeError(f"supabase {what}: retries exhausted")

    # ------------------------------------------------------------------ startup
    def preflight(self, host: str, beat: bool = True) -> list[str]:
        """Everything the worker needs, checked before it claims any job. -> list of problems (empty = ready).
        Write permissions are probed without writing: an update matching no row, inserts that a foreign key
        rejects (409 = allowed but no such job; 403 = the grant is missing)."""
        problems = []
        for t in TABLES:
            try:
                r = self._send("GET", f"/rest/v1/{t}", what=f"read {t}", tries=2, params={"select": "*", "limit": "0"},
                               headers=self.h)
            except httpx.HTTPError as e:
                return [f"cannot reach Supabase at SUPABASE_URL: {type(e).__name__} ({str(e)[:80]})"]
            if r.status_code >= 300:
                problems.append(explain(r.status_code, r.text, f"table {t}"))
        for what, method, path, kw in (
                ("update jobs", "PATCH", "/rest/v1/jobs",
                 {"params": {"id": f"eq.{NIL}", "select": "id"}, "json": {"error": None},
                  "headers": {**self.h, "Prefer": "return=representation"}}),
                ("insert job_events", "POST", "/rest/v1/job_events",
                 {"json": {"job_id": NIL, "user_id": NIL, "stage": "preflight", "message": "preflight"},
                  "headers": {**self.h, "Prefer": "return=minimal"}}),
                ("insert sites", "POST", "/rest/v1/sites",
                 {"json": {"job_id": NIL, "user_id": NIL, "html_path": "preflight", "css_path": "preflight"},
                  "headers": {**self.h, "Prefer": "return=minimal"}})):
            r = self._send(method, path, what=what, tries=2, **kw)
            if r.status_code in (401, 403) or "42501" in r.text:
                problems.append(explain(r.status_code, r.text, what))
            elif r.status_code in (200, 201, 204) and method == "POST":   # no FK on this project: undo the probe
                self._send("DELETE", path, what=f"undo {what}", tries=2,
                           params={"job_id": f"eq.{NIL}"}, headers=self.h)
        r = self._send("GET", "/storage/v1/bucket/sites", what="bucket", tries=2, headers=self.h)
        if r.status_code >= 300:
            problems.append(explain(r.status_code, r.text, "storage bucket 'sites'"))
        if beat:                                        # doctor skips it: it would show the engine as online
            r = self._beat(host, "idle", None)
            if r is not None and r.status_code >= 300:
                problems.append(explain(r.status_code, r.text, "engine_status heartbeat"))
        return list(dict.fromkeys(problems))

    def recover(self, host: str) -> tuple[int, int]:
        """Jobs this machine claimed but never finished (crash, Ctrl+C, a failed write): retry or fail them now
        instead of waiting for the 15-minute stale sweep. -> (requeued, failed)."""
        base = {"worker_id": f"like.{host}-*", "status": f"in.{ACTIVE}", "select": "id"}
        h = {**self.h, "Prefer": "return=representation"}
        failed = self._ok(self._send("PATCH", "/rest/v1/jobs", what="recover", params={**base, "attempts": "gte.2"},
                                     headers=h, json={"status": "failed", "error": "the engine restarted during this job",
                                                      "finished_at": now_iso()})).json()
        requeued = self._ok(self._send("PATCH", "/rest/v1/jobs", what="recover", params=base, headers=h,
                                       json={"status": "queued", "worker_id": None})).json()
        return len(requeued), len(failed)

    def requeue_mine(self, worker_id: str) -> int:
        """After a claim whose reply was lost: put back anything this worker process may have claimed (it is not
        working on anything at that moment). Best effort. -> jobs re-queued."""
        try:
            r = self._ok(self._send("PATCH", "/rest/v1/jobs", what="requeue", tries=3,
                                    params={"worker_id": f"eq.{worker_id}", "status": f"in.{ACTIVE}", "select": "id"},
                                    json={"status": "queued", "worker_id": None},
                                    headers={**self.h, "Prefer": "return=representation"}))
            return len(r.json())
        except Exception as e:  # noqa: BLE001
            print(f"warning: could not re-queue after a failed claim ({str(e)[:120]})", flush=True)
            return 0

    # ------------------------------------------------------------------ jobs
    def claim(self, worker_id: str) -> dict | None:
        """Not idempotent: never retried here (the caller re-queues with requeue_mine on a network error)."""
        r = self._ok(self._send("POST", "/rest/v1/rpc/claim_job", what="claim", tries=1, json={"worker": worker_id},
                                headers=self.h))
        rows = r.json()
        return rows[0] if rows else None

    def update_job(self, job_id: str, *, _tries: int = 4, _timeout: float | None = None, **fields) -> int:
        """Strict update of a job that is still open. -> rows changed (0 = it was already done or cancelled)."""
        kw = {"timeout": _timeout} if _timeout else {}
        r = self._ok(self._send("PATCH", "/rest/v1/jobs", what="update job", tries=_tries,
                                params={"id": f"eq.{job_id}", "status": OPEN, "select": "id"},
                                json=fields, headers={**self.h, "Prefer": "return=representation"}, **kw))
        return len(r.json())

    def progress(self, job_id: str, status: str) -> None:
        """Best-effort stage update (UI only): one retry and a short timeout, so a network drop costs the job
        seconds, not the 4 tries x 60 s a strict write may take."""
        try:
            self.update_job(job_id, status=status, _tries=2, _timeout=15)
        except Exception as e:  # noqa: BLE001
            print(f"warning: stage update failed ({str(e)[:160]})", flush=True)

    def job_status(self, job_id: str) -> str | None:
        r = self._ok(self._send("GET", "/rest/v1/jobs", what="job status",
                                params={"id": f"eq.{job_id}", "select": "status"}, headers=self.h))
        rows = r.json()
        return rows[0]["status"] if rows else None

    def event(self, job: dict, stage: str, message: str, data: dict | None = None) -> None:
        """Best-effort progress event (UI only): one retry, then a failure is logged and the job carries on."""
        try:
            self._ok(self._send("POST", "/rest/v1/job_events", what="event", tries=2, timeout=15,
                                json={"job_id": job["id"], "user_id": job["user_id"], "stage": stage,
                                      "message": message[:500], "data": data},
                                headers={**self.h, "Prefer": "return=minimal"}))
        except Exception as e:  # noqa: BLE001
            print(f"warning: event '{stage}' not recorded ({str(e)[:160]})", flush=True)

    def insert_site(self, row: dict) -> dict:
        h = {**self.h, "Prefer": "return=representation"}
        r = self._send("POST", "/rest/v1/sites", what="insert site", json=row, headers=h)
        if r.status_code >= 300 and "mockup_path" in row and "mockup_path" in r.text:
            # migration 20261121000000_site_mockups.sql not applied yet: keep the site, drop the mockup link
            print("sites.mockup_path missing: run supabase/migrations/20261121000000_site_mockups.sql", flush=True)
            row = {k: v for k, v in row.items() if k != "mockup_path"}
            r = self._send("POST", "/rest/v1/sites", what="insert site", json=row, headers=h)
        if r.status_code == 409 and ("23505" in r.text or "duplicate" in r.text.lower()):
            # unique job_id: an earlier attempt (e.g. one whose reply was lost) already saved this job's site
            got = self._ok(self._send("GET", "/rest/v1/sites", what="find site",
                                      params={"job_id": f"eq.{row['job_id']}", "select": "*"}, headers=self.h)).json()
            if got:
                return got[0]
        return self._ok(r).json()[0]

    # ------------------------------------------------------------------ heartbeat + storage
    def _beat(self, worker_id: str, state: str, section_mode: str | None) -> httpx.Response | None:
        row = {"worker_id": worker_id, "state": state, "last_seen": now_iso()}
        if section_mode:
            row["section_mode"] = section_mode
        try:
            return self._send("POST", "/rest/v1/engine_status", what="heartbeat", tries=2, json=row,
                              headers={**self.h, "Prefer": "resolution=merge-duplicates,return=minimal"}, timeout=15)
        except httpx.HTTPError:
            return None

    def heartbeat(self, worker_id: str, state: str, section_mode: str | None = None) -> None:
        """Upsert this machine's engine_status row (idle|busy|offline). Never raises; the first refusal is logged
        so a silent permission problem can't make the studio badge lie."""
        r = self._beat(worker_id, state, section_mode)
        if r is not None and r.status_code >= 300 and not self._beat_warned:
            self._beat_warned = True
            print("warning: " + explain(r.status_code, r.text, "engine_status heartbeat"), flush=True)

    def pulse(self, worker_id: str, section_mode: str | None = None, every: float = 15.0) -> "Pulse":
        """A background heartbeat on its own connection (see Pulse)."""
        return Pulse(Supa(self._transport, self.sleep), worker_id, section_mode, every)

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        """Upsert (x-upsert), so a retry after a lost reply is harmless."""
        self._ok(self._send("POST", f"/storage/v1/object/sites/{quote(path)}", what=f"upload {path.rsplit('/', 1)[-1]}",
                            content=data, headers={**self.h, "Content-Type": content_type, "x-upsert": "true",
                                                   "Cache-Control": "max-age=3600"}))

    def delete_object(self, path: str) -> None:
        self._ok(self._send("DELETE", "/storage/v1/object/sites", what="delete object", json={"prefixes": [path]},
                            headers=self.h))


class Pulse:
    """The engine heartbeat on its own thread and connection: engine_status is upserted every `every` seconds with
    the current state, whatever the main thread is doing (a long model call, browser QA, the mockup screenshot), so
    the studio badge never reads "offline" in the middle of a generation. set() beats at once when the state
    changes; stop() sends the final state (offline) right away. A failed beat is simply retried on the next tick."""

    def __init__(self, sb: "Supa", worker_id: str, section_mode: str | None = None, every: float = 20.0):
        self.sb, self.worker_id, self.mode, self.every = sb, worker_id, section_mode, every
        self.state = "idle"
        self.beats = 0
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="engine-heartbeat", daemon=True)

    def start(self) -> "Pulse":
        self._thread.start()
        return self

    def set(self, state: str) -> None:
        if state != self.state:
            self.state = state
            self._wake.set()

    def _beat(self) -> None:
        with self._lock:
            try:
                self.sb.heartbeat(self.worker_id, self.state, self.mode)
                self.beats += 1
            except Exception as e:  # noqa: BLE001 - heartbeat() never raises by design; belt and braces
                print(f"warning: heartbeat failed ({type(e).__name__}: {str(e)[:90]})", flush=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._beat()
            self._wake.wait(self.every)
            self._wake.clear()

    def stop(self, final: str = "offline") -> None:
        self._stop.set()
        self._wake.set()
        self._thread.join(timeout=5)
        self.state = final
        self._beat()
