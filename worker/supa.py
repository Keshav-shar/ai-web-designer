"""supa.py - the few Supabase calls the worker makes, over plain REST (PostgREST + Storage) with httpx.

Env only: SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY. The service-role key stays on this PC; the web app never has it.
"""
from __future__ import annotations

import os
from urllib.parse import quote

import httpx


class Supa:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        if not (self.url and key):
            raise RuntimeError("set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in the worker's environment")
        self.h = {"apikey": key, "Authorization": f"Bearer {key}"}
        self.http = httpx.Client(timeout=httpx.Timeout(60, connect=15))

    def _ok(self, r: httpx.Response) -> httpx.Response:
        if r.status_code >= 300:
            raise RuntimeError(f"supabase {r.request.method} {r.request.url.path}: {r.status_code} {r.text[:300]}")
        return r

    def claim(self, worker_id: str) -> dict | None:
        r = self._ok(self.http.post(f"{self.url}/rest/v1/rpc/claim_job", json={"worker": worker_id}, headers=self.h))
        rows = r.json()
        return rows[0] if rows else None

    def update_job(self, job_id: str, **fields) -> None:
        self._ok(self.http.patch(f"{self.url}/rest/v1/jobs", params={"id": f"eq.{job_id}"}, json=fields,
                                 headers={**self.h, "Prefer": "return=minimal"}))

    def event(self, job: dict, stage: str, message: str, data: dict | None = None) -> None:
        self._ok(self.http.post(f"{self.url}/rest/v1/job_events",
                                json={"job_id": job["id"], "user_id": job["user_id"], "stage": stage,
                                      "message": message[:500], "data": data},
                                headers={**self.h, "Prefer": "return=minimal"}))

    def insert_site(self, row: dict) -> dict:
        h = {**self.h, "Prefer": "return=representation"}
        r = self.http.post(f"{self.url}/rest/v1/sites", json=row, headers=h)
        if r.status_code >= 300 and "mockup_path" in row and "mockup_path" in r.text:
            # migration 20261121000000_site_mockups.sql not applied yet: keep the site, drop the mockup link
            print("sites.mockup_path missing: run supabase/migrations/20261121000000_site_mockups.sql", flush=True)
            r = self.http.post(f"{self.url}/rest/v1/sites", json={k: v for k, v in row.items() if k != "mockup_path"},
                               headers=h)
        return self._ok(r).json()[0]

    def heartbeat(self, worker_id: str, state: str, section_mode: str | None = None) -> None:
        """Upsert this worker's engine_status row (state idle|busy|offline). Never raises: a missed beat only
        makes the studio badge show offline for a moment."""
        from datetime import datetime, timezone
        row = {"worker_id": worker_id, "state": state, "last_seen": datetime.now(timezone.utc).isoformat()}
        if section_mode:
            row["section_mode"] = section_mode
        try:
            self.http.post(f"{self.url}/rest/v1/engine_status", json=row,
                           headers={**self.h, "Prefer": "resolution=merge-duplicates,return=minimal"}, timeout=15)
        except httpx.HTTPError:
            pass

    def upload(self, path: str, data: bytes, content_type: str) -> None:
        self._ok(self.http.post(f"{self.url}/storage/v1/object/sites/{quote(path)}", content=data,
                                headers={**self.h, "Content-Type": content_type, "x-upsert": "true",
                                         "Cache-Control": "max-age=3600"}))
