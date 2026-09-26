-- Keep the admin check out of the public API: it moves to a private schema that the REST API
-- does not expose. approve_user() and acknowledge_intended_use() stay callable on purpose — they
-- are the website's only two write actions, and each checks who is calling before it writes.
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;

create function private.is_admin()
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
revoke all on function private.is_admin() from public, anon;
grant execute on function private.is_admin() to authenticated;

drop policy "admins read all profiles" on public.profiles;
create policy "admins read all profiles" on public.profiles
  for select to authenticated using ((select private.is_admin()));

create or replace function public.approve_user(target uuid, approve boolean)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if not private.is_admin() then
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

drop function public.is_admin();
