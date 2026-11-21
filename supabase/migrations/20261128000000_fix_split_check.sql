-- Fix for 20261126000000_worker_split.sql: that migration made jobs.split nullable so the browser inserts only the
-- prompt, and assumed the old check "evaluates to NULL for a NULL split". It does not:
--   char_length(coalesce(NULL ->> 'full_query', '')) between 1 and 300   ->  0 between 1 and 300  ->  FALSE
-- and NULL AND FALSE is FALSE, so every new job was rejected (23514 jobs_split_check) and nothing reached the queue.
-- Now a missing split is allowed explicitly; a split the worker writes back is checked exactly as before.
alter table public.jobs drop constraint if exists jobs_split_check;
alter table public.jobs add constraint jobs_split_check check (
  split is null or (
    jsonb_typeof(split) = 'object'
    and char_length(coalesce(split ->> 'full_query', '')) between 1 and 300
    and char_length(coalesce(split ->> 'vibe_query', '')) between 1 and 300));
