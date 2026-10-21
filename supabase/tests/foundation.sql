-- Run on the disposable LOCAL development database as the migration owner:
-- psql -h 127.0.0.1 -p 54322 -U postgres -d postgres -v ON_ERROR_STOP=1 -f supabase/tests/foundation.sql
-- All test records roll back. This script is not a concurrency or full API acceptance test.
\set ON_ERROR_STOP on
begin;

create function pg_temp.assert_true(ok boolean, message text) returns void language plpgsql as $$
begin
  if ok is distinct from true then raise exception 'ASSERTION FAILED: %', message; end if;
end $$;

select pg_temp.assert_true((select not rolsuper and not rolbypassrls and not rolcreatedb and not rolcreaterole from pg_roles where rolname = 'eventra_app'), 'runtime role is restricted');
select pg_temp.assert_true((select count(*) = 3 from pg_extension where extname in ('postgis', 'vector', 'btree_gist')), 'required extensions installed');
select pg_temp.assert_true(not exists (select 1 from pg_tables where schemaname = 'app' and not rowsecurity), 'every app table has RLS');
select pg_temp.assert_true((select atttypmod = 1024 from pg_attribute where attrelid = 'app.artist_embeddings'::regclass and attname = 'embedding'), 'embedding dimensions are 1024');

-- The Auth trigger must ignore the forged admin metadata.
insert into auth.users (id, email, raw_user_meta_data) values
  ('10000000-0000-4000-8000-000000000001', 'organizer-a@example.invalid', '{"display_name":"Organizer A","role":"admin","is_admin":true}'),
  ('10000000-0000-4000-8000-000000000002', 'organizer-b@example.invalid', '{"display_name":"Organizer B"}'),
  ('10000000-0000-4000-8000-000000000003', 'artist@example.invalid', '{"display_name":"Artist Owner"}'),
  ('10000000-0000-4000-8000-000000000004', 'draft-artist@example.invalid', '{"display_name":"Draft Artist Owner"}');
select pg_temp.assert_true(not exists (select 1 from app.user_roles where user_id = '10000000-0000-4000-8000-000000000001' and role = 'admin'), 'metadata cannot grant admin');

insert into app.artists (id, owner_id, slug, name, category, city, tagline, description, price_paise, status) values
  ('20000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000003', 'test-public-artist', 'Test public artist', 'DJ', 'Pune', 'SQL fixture', 'Disposable SQL fixture', 100000, 'published'),
  ('20000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000004', 'test-draft-artist', 'Test draft artist', 'DJ', 'Pune', 'SQL fixture', 'Disposable SQL fixture', 100000, 'draft');

insert into app.event_briefs (id, organizer_id, title, city, during) values
  ('30000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', 'First event', 'Pune', tstzrange(now() + interval '1 day', now() + interval '1 day 2 hours', '[)')),
  ('30000000-0000-4000-8000-000000000002', '10000000-0000-4000-8000-000000000002', 'Overlap event', 'Pune', tstzrange(now() + interval '1 day 1 hour', now() + interval '1 day 3 hours', '[)')),
  ('30000000-0000-4000-8000-000000000003', '10000000-0000-4000-8000-000000000002', 'Adjacent event', 'Pune', tstzrange(now() + interval '1 day 3 hours', now() + interval '1 day 5 hours', '[)'));

insert into app.conversations (id, event_id, artist_id, organizer_id)
select ('40000000-0000-4000-8000-' || lpad(right(id::text, 1), 12, '0'))::uuid, id, '20000000-0000-4000-8000-000000000001', organizer_id
from app.event_briefs where id::text like '30000000-0000-4000-8000-%';
insert into app.conversation_members (conversation_id, user_id)
select id, organizer_id from app.conversations where id::text like '40000000-0000-4000-8000-%';
insert into app.conversation_members (conversation_id, user_id)
select id, '10000000-0000-4000-8000-000000000003' from app.conversations where id::text like '40000000-0000-4000-8000-%';

insert into app.quotes (id, conversation_id, event_id, artist_id, organizer_id, version, performance_paise, total_paise, performance_during, occupied_during, terms, expires_at)
select ('50000000-0000-4000-8000-' || lpad(right(c.id::text, 1), 12, '0'))::uuid, c.id, c.event_id, c.artist_id, c.organizer_id, 1, 100000, 100000, e.during,
  case when right(c.id::text, 1) = '1' then tstzrange(lower(e.during) - interval '30 minutes', upper(e.during) + interval '30 minutes', '[)')
    when right(c.id::text, 1) = '3' then tstzrange(now() + interval '1 day 2 hours 30 minutes', upper(e.during), '[)')
    else e.during end,
  'Synthetic immutable test quote', now() + interval '1 hour'
from app.conversations c join app.event_briefs e on e.id = c.event_id where c.id::text like '40000000-0000-4000-8000-%';

do $$ begin
  update app.quotes set total_paise = 1 where id = '50000000-0000-4000-8000-000000000001';
  raise exception 'Expected immutable quote rejection';
exception when check_violation then null; end $$;

do $$ begin
  insert into app.quote_acceptances (quote_id, organizer_id, idempotency_key)
  values ('50000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000002', 'wrong-owner-acceptance');
  raise exception 'Expected quote owner mismatch';
exception when check_violation then null; end $$;

insert into app.quote_acceptances (quote_id, organizer_id, idempotency_key)
select id, organizer_id, 'test-accept-' || id::text from app.quotes where id::text like '50000000-0000-4000-8000-%';
insert into app.reservations (id, quote_id, artist_id, organizer_id, occupied_during, expires_at)
select '60000000-0000-4000-8000-000000000001', id, artist_id, organizer_id, occupied_during, clock_timestamp() + interval '5 minutes'
from app.quotes where id = '50000000-0000-4000-8000-000000000001';

do $$ begin
  insert into app.reservations (quote_id, artist_id, organizer_id, occupied_during, expires_at)
  select id, artist_id, organizer_id, occupied_during, clock_timestamp() + interval '5 minutes'
  from app.quotes where id = '50000000-0000-4000-8000-000000000002';
  raise exception 'Expected overlapping occupied interval rejection';
exception when exclusion_violation then null; end $$;

-- A half-open interval beginning at the previous upper bound is legal.
insert into app.reservations (id, quote_id, artist_id, organizer_id, occupied_during, expires_at)
select '60000000-0000-4000-8000-000000000003', id, artist_id, organizer_id, occupied_during, clock_timestamp() + interval '5 minutes'
from app.quotes where id = '50000000-0000-4000-8000-000000000003';

do $$ begin
  update app.reservations set status = 'confirmed' where id = '60000000-0000-4000-8000-000000000001';
  raise exception 'Expected confirmation without capture rejection';
exception when check_violation then null; end $$;

do $$ begin
  insert into app.bookings (reservation_id, quote_id, artist_id, organizer_id, total_paise)
  select r.id, r.quote_id, r.artist_id, r.organizer_id, 1 from app.reservations r where r.id = '60000000-0000-4000-8000-000000000001';
  raise exception 'Expected altered booking price rejection';
exception when check_violation then null; end $$;

insert into app.bookings (id, reservation_id, quote_id, artist_id, organizer_id, total_paise)
select '70000000-0000-4000-8000-000000000001', r.id, r.quote_id, r.artist_id, r.organizer_id, q.total_paise
from app.reservations r join app.quotes q on q.id = r.quote_id where r.id = '60000000-0000-4000-8000-000000000001';

do $$ begin
  insert into app.payment_attempts (booking_id, provider_order_id, idempotency_key, amount_paise)
  values ('70000000-0000-4000-8000-000000000001', 'wrong-order', 'wrong-attempt', 1);
  raise exception 'Expected payment amount mismatch rejection';
exception when check_violation then null; end $$;

insert into app.payment_attempts (id, booking_id, provider_order_id, idempotency_key, amount_paise)
values ('80000000-0000-4000-8000-000000000001', '70000000-0000-4000-8000-000000000001', 'test-order-1', 'test-attempt-1', 100000);
insert into app.payments (id, attempt_id, booking_id, amount_paise, provider_event_id)
values ('90000000-0000-4000-8000-000000000001', '80000000-0000-4000-8000-000000000001', '70000000-0000-4000-8000-000000000001', 100000, 'test-capture-1');
select pg_temp.assert_true((select not requires_review from app.payments where id = '90000000-0000-4000-8000-000000000001'), 'live capture is valid');
update app.reservations set status = 'confirmed' where id = '60000000-0000-4000-8000-000000000001';
update app.bookings set status = 'confirmed' where id = '70000000-0000-4000-8000-000000000001';

do $$ begin
  insert into app.payments (attempt_id, booking_id, amount_paise, provider_event_id)
  values ('80000000-0000-4000-8000-000000000001', '70000000-0000-4000-8000-000000000001', 100000, 'test-capture-1');
  raise exception 'Expected duplicate capture rejection';
exception when unique_violation then null; end $$;

insert into app.refunds (payment_id, amount_paise, idempotency_key)
values ('90000000-0000-4000-8000-000000000001', 60000, 'refund-first');
do $$ begin
  insert into app.refunds (payment_id, amount_paise, idempotency_key)
  values ('90000000-0000-4000-8000-000000000001', 50000, 'refund-too-much');
  raise exception 'Expected over-refund rejection';
exception when check_violation then null; end $$;

do $$ begin
  insert into app.reviews (booking_id, organizer_id, artist_id, stars, body)
  values ('70000000-0000-4000-8000-000000000001', '10000000-0000-4000-8000-000000000001', '20000000-0000-4000-8000-000000000001', 5, 'Premature review');
  raise exception 'Expected review before completion rejection';
exception when check_violation then null; end $$;

-- Verified subject is set only by a future JWT-validating backend, transaction-locally.
set local role eventra_app;
select set_config('request.jwt.claims', '{"sub":"10000000-0000-4000-8000-000000000001","role":"authenticated"}', true);
select pg_temp.assert_true((select count(*) = 1 from app.profiles), 'runtime sees only own profile');
select pg_temp.assert_true((select count(*) = 1 from app.event_briefs), 'runtime sees only own event');
select pg_temp.assert_true((select count(*) = 1 from app.quotes), 'runtime sees only own quote');
select pg_temp.assert_true(exists (select 1 from public.artist_catalogue_preview where slug = 'test-public-artist'), 'published catalogue visible');
select pg_temp.assert_true(not exists (select 1 from public.artist_catalogue_preview where slug = 'test-draft-artist'), 'draft catalogue hidden');
do $$ begin
  perform owner_id from app.artists limit 1;
  raise exception 'Expected private artist column rejection';
exception when insufficient_privilege then null; end $$;
do $$ begin
  insert into app.user_roles (user_id, role) values ('10000000-0000-4000-8000-000000000001', 'admin');
  raise exception 'Expected self-promotion rejection';
exception when insufficient_privilege then null; end $$;
do $$ begin
  update app.bookings set status = 'completed' where id = '70000000-0000-4000-8000-000000000001';
  raise exception 'Expected runtime business mutation rejection';
exception when insufficient_privilege then null; end $$;
reset role;

set local role authenticated;
select pg_temp.assert_true((select count(*) = 1 from app.profiles), 'authenticated role also obeys RLS');
reset role;

-- A second actor must not inherit the first actor's profile or quote.
set local role eventra_app;
select set_config('request.jwt.claims', '{"sub":"10000000-0000-4000-8000-000000000002","role":"authenticated"}', true);
select pg_temp.assert_true(not exists (select 1 from app.profiles where id = '10000000-0000-4000-8000-000000000001'), 'cross-user profile hidden');
select pg_temp.assert_true(not exists (select 1 from app.quotes where id = '50000000-0000-4000-8000-000000000001'), 'cross-user quote hidden');
reset role;
rollback;

-- SET LOCAL must not leave a subject on the next transaction in this connection.
begin;
set local role eventra_app;
do $$ begin
  -- Managed postgres cannot grant runtime schema lookup on platform-owned auth.
  -- Inspect both transaction-local claims directly; policies use bound auth.uid().
  if nullif(current_setting('request.jwt.claim.sub',true),'') is not null
    or nullif(current_setting('request.jwt.claims',true),'') is not null then
    raise exception 'Transaction-local identity leaked';
  end if;
end $$;
reset role;
rollback;
\echo Foundation assertions passed; all disposable records rolled back.
