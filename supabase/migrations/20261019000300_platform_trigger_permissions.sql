-- Supabase installs this event trigger on newer projects. It should not be an RPC.
-- Keep the trigger and its automatic RLS protection; restrict direct invocation.
begin;
do $$
begin
  if to_regprocedure('public.rls_auto_enable()') is not null then
    revoke execute on function public.rls_auto_enable() from public, anon, authenticated;
  end if;
end $$;
commit;
