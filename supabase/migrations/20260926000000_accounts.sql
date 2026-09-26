-- DiaCausal website accounts (Supabase project "diacausal", ap-south-1).
-- Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.
--
-- Anyone may sign up; an admin must approve each account before it can use "Try it" or "Evidence".
-- This table holds names, emails, roles and approval dates only: never patient values, questions or results.

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  full_name text not null check (char_length(full_name) between 1 and 120),
  email text not null,
  role text not null check (role in ('clinician', 'student', 'examiner')),
  approved boolean not null default false,
  rejected boolean not null default false,
  is_admin boolean not null default false,
  approved_at timestamptz,
  approved_by uuid references auth.users (id),
  intended_use_ack_at timestamptz,
  created_at timestamptz not null default now()
);

comment on table public.profiles is
  'DiaCausal website accounts: approval status only. Never patient values, questions or results.';

alter table public.profiles enable row level security;

-- Is the signed-in person an admin who has passed the authenticator-app step (AAL2)?
create function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select coalesce(
    (select p.is_admin from public.profiles p where p.id = (select auth.uid()))
    and coalesce((select auth.jwt() ->> 'aal'), '') = 'aal2',
    false);
$$;

-- Each person reads their own row; an admin (with MFA) reads every row. Nobody writes directly.
create policy "read own profile" on public.profiles
  for select to authenticated using (id = (select auth.uid()));
create policy "admins read all profiles" on public.profiles
  for select to authenticated using ((select public.is_admin()));

-- A new sign-up gets a profile from its sign-up form (name and role), not approved.
create function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  r text := coalesce(new.raw_user_meta_data ->> 'role', 'student');
begin
  insert into public.profiles (id, full_name, email, role)
  values (
    new.id,
    left(coalesce(nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''), split_part(new.email, '@', 1)), 120),
    new.email,
    case when r in ('clinician', 'student', 'examiner') then r else 'student' end
  );
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- Admin approves (true) or rejects (false) one account. Needs an admin with MFA.
create function public.approve_user(target uuid, approve boolean)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not public.is_admin() then
    raise exception 'only an admin who has entered an authenticator code can approve accounts'
      using errcode = '42501';
  end if;
  update public.profiles
     set approved = approve,
         rejected = not approve,
         approved_at = case when approve then now() else null end,
         approved_by = (select auth.uid())
   where id = target;
end;
$$;

-- The signed-in person records that they read the intended-use statement.
create function public.acknowledge_intended_use()
returns void
language sql
security definer
set search_path = ''
as $$
  update public.profiles set intended_use_ack_at = now() where id = (select auth.uid());
$$;

revoke all on function public.is_admin() from public, anon;
revoke all on function public.approve_user(uuid, boolean) from public, anon;
revoke all on function public.acknowledge_intended_use() from public, anon;
revoke all on function public.handle_new_user() from public, anon, authenticated;
grant execute on function public.is_admin() to authenticated;
grant execute on function public.approve_user(uuid, boolean) to authenticated;
grant execute on function public.acknowledge_intended_use() to authenticated;

revoke all on table public.profiles from anon;
revoke insert, update, delete on table public.profiles from authenticated;
grant select on table public.profiles to authenticated;
