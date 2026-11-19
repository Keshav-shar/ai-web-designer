-- serpman Studio: jobs queue, sites, live events, private storage.
-- Trust model: browsers (authenticated role) may only INSERT a prompt and READ their own rows; every state
-- change is made by the PC worker with the service role, which never leaves that machine.

create extension if not exists pgcrypto;

create type public.job_status as enum ('queued', 'routing', 'recipe', 'generating', 'assembling', 'done', 'failed');

-- ---------------------------------------------------------------- profiles
create table public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  daily_quota int  not null default 5 check (daily_quota between 0 and 100),
  created_at  timestamptz not null default now()
);

create function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.profiles (id) values (new.id) on conflict do nothing;
  return new;
end $$;

create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------- jobs
create table public.jobs (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null default auth.uid() references auth.users (id) on delete cascade,
  prompt      text not null check (char_length(prompt) between 3 and 300),
  split       jsonb not null check (
                jsonb_typeof(split) = 'object'
                and char_length(coalesce(split ->> 'full_query', '')) between 1 and 300
                and char_length(coalesce(split ->> 'vibe_query', '')) between 1 and 300),
  brief       jsonb,
  status      public.job_status not null default 'queued',
  error       text,
  attempts    int  not null default 0,
  worker_id   text,
  created_at  timestamptz not null default now(),
  claimed_at  timestamptz,
  finished_at timestamptz
);
create index jobs_queue_idx on public.jobs (status, created_at);
create index jobs_user_idx  on public.jobs (user_id, created_at desc);

-- ---------------------------------------------------------------- sites
create table public.sites (
  id         uuid primary key default gen_random_uuid(),
  job_id     uuid not null unique references public.jobs (id) on delete cascade,
  user_id    uuid not null references auth.users (id) on delete cascade,
  title      text,
  html_path  text not null,
  css_path   text not null,
  created_at timestamptz not null default now()
);
create index sites_user_idx on public.sites (user_id, created_at desc);

-- ---------------------------------------------------------------- job events (live timeline)
create table public.job_events (
  id      bigint generated always as identity primary key,
  job_id  uuid not null references public.jobs (id) on delete cascade,
  user_id uuid not null references auth.users (id) on delete cascade,
  stage   text not null,
  message text not null,
  data    jsonb,
  ts      timestamptz not null default now()
);
create index job_events_job_idx on public.job_events (job_id, id);

-- ---------------------------------------------------------------- row level security
alter table public.profiles   enable row level security;
alter table public.jobs       enable row level security;
alter table public.sites      enable row level security;
alter table public.job_events enable row level security;

create policy "own profile"  on public.profiles   for select to authenticated using (id = (select auth.uid()));
create policy "own jobs"     on public.jobs       for select to authenticated using (user_id = (select auth.uid()));
create policy "own sites"    on public.sites      for select to authenticated using (user_id = (select auth.uid()));
create policy "own events"   on public.job_events for select to authenticated using (user_id = (select auth.uid()));
create policy "queue a job"  on public.jobs       for insert to authenticated with check (user_id = (select auth.uid()));

-- Column privileges: a browser can set only prompt + split; status, brief, worker fields keep their defaults.
revoke all on public.jobs, public.sites, public.job_events, public.profiles from anon, authenticated;
grant select on public.jobs, public.sites, public.job_events, public.profiles to authenticated;
grant insert (prompt, split) on public.jobs to authenticated;

-- ---------------------------------------------------------------- quota + one running job per user
create function public.enforce_job_quota() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  quota int;
  used  int;
begin
  perform pg_advisory_xact_lock(hashtextextended(new.user_id::text, 0));   -- serialise one user's inserts
  select daily_quota into quota from public.profiles where id = new.user_id;
  if quota is null then
    raise exception 'no profile for this user' using errcode = 'P0001';
  end if;
  if exists (select 1 from public.jobs
             where user_id = new.user_id and status not in ('done', 'failed')) then
    raise exception 'a job is already running' using errcode = 'P0001', hint = 'wait for it to finish';
  end if;
  select count(*) into used from public.jobs
   where user_id = new.user_id and created_at > now() - interval '24 hours';
  if used >= quota then
    raise exception 'daily quota reached (% per 24h)', quota using errcode = 'P0001';
  end if;
  return new;
end $$;

create trigger jobs_quota before insert on public.jobs
  for each row execute function public.enforce_job_quota();

-- ---------------------------------------------------------------- worker queue (service role only)
create function public.claim_job(worker text) returns setof public.jobs
language plpgsql security definer set search_path = '' as $$
begin
  -- stale claims (worker died / PC slept): retry once, then fail
  update public.jobs set status = 'failed', error = 'worker stopped responding', finished_at = now()
   where status in ('routing', 'recipe', 'generating', 'assembling')
     and claimed_at < now() - interval '15 minutes' and attempts >= 2;
  update public.jobs set status = 'queued', worker_id = null
   where status in ('routing', 'recipe', 'generating', 'assembling')
     and claimed_at < now() - interval '15 minutes' and attempts < 2;

  return query
  update public.jobs j
     set status = 'routing', worker_id = worker, claimed_at = now(), attempts = j.attempts + 1
   where j.id = (select id from public.jobs
                  where status = 'queued' order by created_at
                  for update skip locked limit 1)
  returning j.*;
end $$;

revoke execute on function public.claim_job(text) from public, anon, authenticated;
grant execute on function public.claim_job(text) to service_role;
revoke execute on function public.enforce_job_quota() from public, anon, authenticated;
revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- ---------------------------------------------------------------- realtime (RLS applies to subscribers)
alter publication supabase_realtime add table public.job_events, public.jobs;

-- ---------------------------------------------------------------- storage: private bucket, owner-folder reads
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('sites', 'sites', false, 10485760,
        array['text/html', 'text/css', 'image/jpeg', 'image/png', 'image/webp', 'image/avif', 'image/gif'])
on conflict (id) do nothing;

create policy "read own site files" on storage.objects for select to authenticated
  using (bucket_id = 'sites' and (storage.foldername(name))[1] = (select auth.uid())::text);
