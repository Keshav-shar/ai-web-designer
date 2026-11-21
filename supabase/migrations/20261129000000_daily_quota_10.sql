-- Daily site quota per account: 5 -> 10 (sites per 24 h, enforced by enforce_job_quota()).
-- New accounts get 10; existing accounts still on the old default of 5 move to 10. Accounts given a custom quota
-- (create_user.py --quota, or set in the dashboard) keep theirs.
alter table public.profiles alter column daily_quota set default 10;
update public.profiles set daily_quota = 10 where daily_quota = 5;
