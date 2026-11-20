-- 1) Prompts are at most 200 characters (the studio box and the API enforce the same limit).
--    NOT VALID: rows that already exist are left alone; every new job is checked.
alter table public.jobs drop constraint if exists jobs_prompt_check;
alter table public.jobs add constraint jobs_prompt_check check (char_length(prompt) between 3 and 200) not valid;

-- 2) A user can cancel their own queued / running job, so a stuck or unwanted job never blocks new requests
--    (only one active job per user is allowed). The worker re-checks the status before saving a site.
create or replace function public.cancel_job(job uuid) returns boolean
language plpgsql security definer set search_path = '' as $$
declare
  owner uuid;
begin
  update public.jobs
     set status = 'failed', error = 'cancelled by the user', finished_at = now()
   where id = job and user_id = (select auth.uid()) and status not in ('done', 'failed')
  returning user_id into owner;
  if owner is null then
    return false;
  end if;
  insert into public.job_events (job_id, user_id, stage, message)
  values (job, owner, 'failed', 'Cancelled.');
  return true;
end $$;

revoke execute on function public.cancel_job(uuid) from public, anon;
grant execute on function public.cancel_job(uuid) to authenticated;
