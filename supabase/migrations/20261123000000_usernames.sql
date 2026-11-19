-- Username accounts: users sign in with a username + password. Supabase Auth still needs an email-shaped login ID,
-- so each username maps to `<username>@<LOGIN_ID_DOMAIN>` (a placeholder, never shown or emailed). The username
-- itself lives here, taken from the account's metadata (tools/create_user.py sets it) or the login ID's local part.

alter table public.profiles add column if not exists username text;
alter table public.profiles drop constraint if exists profiles_username_format;
alter table public.profiles add constraint profiles_username_format
  check (username is null or username ~ '^[a-z0-9._-]{3,24}$');
create unique index if not exists profiles_username_key on public.profiles (username);

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  uname text := lower(coalesce(new.raw_user_meta_data ->> 'username', split_part(new.email, '@', 1)));
begin
  if uname is null or uname !~ '^[a-z0-9._-]{3,24}$' then
    uname := null;
  end if;
  insert into public.profiles (id, username) values (new.id, uname)
  on conflict (id) do update set username = coalesce(public.profiles.username, excluded.username);
  return new;
end $$;

revoke execute on function public.handle_new_user() from public, anon, authenticated;

-- backfill accounts created before this migration
update public.profiles p
   set username = lower(coalesce(u.raw_user_meta_data ->> 'username', split_part(u.email, '@', 1)))
  from auth.users u
 where p.id = u.id and p.username is null
   and lower(coalesce(u.raw_user_meta_data ->> 'username', split_part(u.email, '@', 1))) ~ '^[a-z0-9._-]{3,24}$';
