-- Engine heartbeat: the PC worker upserts its row every ~30 s (service role); signed-in users read it so the
-- studio can say "engine online" or "offline: your request waits in the queue".
create table if not exists public.engine_status (
  worker_id    text primary key,
  state        text not null default 'idle' check (state in ('idle', 'busy', 'offline')),
  section_mode text,
  last_seen    timestamptz not null default now()
);

alter table public.engine_status enable row level security;
create policy "engine status is readable when signed in" on public.engine_status
  for select to authenticated using (true);

revoke all on public.engine_status from anon, authenticated;
grant select on public.engine_status to authenticated;

alter publication supabase_realtime add table public.engine_status;
