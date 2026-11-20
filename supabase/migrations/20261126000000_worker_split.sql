-- The worker owns the prompt split (worker/split.py is the only implementation).
-- Before: the web API split the prompt (web/lib/split.ts) and the worker trusted the stored split. A web build
-- that lagged the worker turned "Banana Bread, soft and chewy" into vibe_query "soft and chewy", which routed to
-- sports-high-energy. Now the browser inserts the prompt only; the worker splits it and writes back the split it
-- actually routed on (service_role keeps full access, see 20261124000000_service_role_grants.sql).
--
-- Order: restart the worker first (it already ignores any stored split), then apply this, then deploy the web.

-- 1) A new job has no split until the worker claims it. The existing check (object with 1..300-char queries)
--    evaluates to NULL for a NULL split, so it still guards every split the worker writes.
alter table public.jobs alter column split drop not null;

-- 2) Browsers can no longer write a split at all; they set the prompt and nothing else.
revoke insert (split) on public.jobs from authenticated;
revoke insert on public.jobs from authenticated;
grant insert (prompt) on public.jobs to authenticated;
