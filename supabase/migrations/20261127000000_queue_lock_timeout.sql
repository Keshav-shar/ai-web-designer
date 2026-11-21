-- The quota trigger serialises one user's inserts with pg_advisory_xact_lock, which waits without limit. If an
-- earlier insert from the same account is stuck holding that lock, every new "Generate" waits behind it and the
-- studio shows "Queuing…" forever. Bound the wait: after 5 s the insert fails with 55P03 (lock_not_available),
-- which the API turns into "The queue didn't answer in time. Please try again."
alter function public.enforce_job_quota() set lock_timeout = '5s';
