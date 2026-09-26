-- Deleting an admin's account must not be blocked by the accounts they approved:
-- keep the approval, forget who gave it.
alter table public.profiles drop constraint profiles_approved_by_fkey;
alter table public.profiles add constraint profiles_approved_by_fkey
  foreign key (approved_by) references auth.users (id) on delete set null;
