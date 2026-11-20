-- Newer Supabase projects no longer grant new public tables to the API roles by default. The worker and
-- tools/create_user.py use the secret (service_role) key, so grant it the app tables explicitly.
-- (RLS still applies to browsers; service_role bypasses RLS by design and never leaves the PC.)
grant usage on schema public to service_role;
grant all on table public.profiles, public.jobs, public.sites, public.job_events, public.engine_status to service_role;
grant usage, select on all sequences in schema public to service_role;
grant execute on function public.claim_job(text) to service_role;
