-- Image mockup per generated site (worker/mockup.py): a 720 px webp of the top of the page, used by the gallery.
alter table public.sites add column if not exists mockup_path text;
