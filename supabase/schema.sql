-- Texas Public Land Hunting — Supabase Auth, profiles, and favorites
-- Run this in the Supabase SQL editor as a project owner (Dashboard → SQL).
-- Do NOT use the service role key in the static web app.

create or replace function public.is_reserved_username(p_username text)
returns boolean
language sql
immutable
as $$
  select lower(p_username) in (
    'admin', 'administrator', 'root', 'system', 'support', 'help',
    'api', 'www', 'mail', 'ftp', 'null', 'undefined', 'anonymous',
    'user', 'users', 'profile', 'account', 'accounts', 'login',
    'signup', 'signin', 'signout', 'logout', 'auth', 'oauth',
    'official', 'tpwd', 'texas', 'moderator', 'mod', 'staff',
    'owner', 'security', 'contact', 'info', 'webmaster', 'postmaster',
    'me', 'you', 'here', 'test', 'guest', 'superuser', 'sysadmin',
    'administrator1', 'about', 'settings', 'config'
  );
$$;

create table if not exists public.profiles (
  user_id uuid primary key references auth.users (id) on delete cascade,
  username text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_username_length check (char_length(username) between 3 and 20),
  constraint profiles_username_format check (username ~ '^[a-z][a-z0-9_]+$'),
  constraint profiles_username_not_reserved check (not public.is_reserved_username(username))
);

create unique index if not exists profiles_username_unique
  on public.profiles (username);

-- Case-insensitive uniqueness (handles are stored lowercase; extra belt)
create unique index if not exists profiles_username_lower_unique
  on public.profiles (lower(username));

create table if not exists public.favorites (
  user_id uuid not null references auth.users (id) on delete cascade,
  unit_id text not null,
  created_at timestamptz not null default now(),
  primary key (user_id, unit_id),
  constraint favorites_unit_id_format check (unit_id ~ '^[A-Za-z0-9._-]{1,64}$')
);

create index if not exists favorites_user_id_idx on public.favorites (user_id);

create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_touch_updated_at on public.profiles;
create trigger profiles_touch_updated_at
  before update on public.profiles
  for each row execute procedure public.touch_updated_at();

-- Copy a validated username from signup metadata, otherwise generate a handle.
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  raw_name text;
  candidate text;
  suffix text;
begin
  raw_name := lower(trim(both from coalesce(new.raw_user_meta_data->>'username', '')));
  if raw_name ~ '^[a-z][a-z0-9_]{2,19}$'
     and not public.is_reserved_username(raw_name)
     and not exists (select 1 from public.profiles p where p.username = raw_name) then
    candidate := raw_name;
  else
    suffix := substr(replace(new.id::text, '-', ''), 1, 12);
    candidate := 'user_' || suffix;
  end if;

  insert into public.profiles (user_id, username)
  values (new.id, candidate)
  on conflict (user_id) do nothing;

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Availability check without granting SELECT on all profiles.
-- The current user's own handle is not reported as taken.
create or replace function public.username_taken(p_username text)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.profiles
    where username = lower(trim(both from coalesce(p_username, '')))
      and user_id is distinct from auth.uid()
  );
$$;

revoke all on function public.username_taken(text) from public;
grant execute on function public.username_taken(text) to anon, authenticated;

alter table public.profiles enable row level security;
alter table public.favorites enable row level security;
alter table public.profiles force row level security;
alter table public.favorites force row level security;

drop policy if exists "profiles_select_own" on public.profiles;
create policy "profiles_select_own"
  on public.profiles for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "profiles_insert_own" on public.profiles;
create policy "profiles_insert_own"
  on public.profiles for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and username ~ '^[a-z][a-z0-9_]{2,19}$'
    and not public.is_reserved_username(username)
  );

drop policy if exists "profiles_update_own" on public.profiles;
create policy "profiles_update_own"
  on public.profiles for update
  to authenticated
  using (auth.uid() = user_id)
  with check (
    auth.uid() = user_id
    and username ~ '^[a-z][a-z0-9_]{2,19}$'
    and not public.is_reserved_username(username)
  );

drop policy if exists "favorites_select_own" on public.favorites;
create policy "favorites_select_own"
  on public.favorites for select
  to authenticated
  using (auth.uid() = user_id);

drop policy if exists "favorites_insert_own" on public.favorites;
create policy "favorites_insert_own"
  on public.favorites for insert
  to authenticated
  with check (
    auth.uid() = user_id
    and unit_id ~ '^[A-Za-z0-9._-]{1,64}$'
  );

drop policy if exists "favorites_delete_own" on public.favorites;
create policy "favorites_delete_own"
  on public.favorites for delete
  to authenticated
  using (auth.uid() = user_id);

revoke all on public.profiles from anon, public;
revoke all on public.favorites from anon, public;
grant select, insert, update on public.profiles to authenticated;
grant select, insert, delete on public.favorites to authenticated;
