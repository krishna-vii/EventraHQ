-- Phase 1 foundation. Migration owner is a maintenance role, never eventra_app.
-- Business write privileges deliberately remain closed until API transactions/tests ship.
begin;

create schema if not exists extensions;
create extension if not exists postgis with schema extensions;
create extension if not exists vector with schema extensions;
create extension if not exists btree_gist with schema extensions;
create schema if not exists app;
revoke all on schema app from public;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'eventra_app') then
    create role eventra_app login nosuperuser nocreatedb nocreaterole noinherit nobypassrls;
  end if;
end $$;
-- Managed Supabase's postgres role cannot reassign SUPERUSER/BYPASSRLS flags.
-- Validate existing attributes instead of issuing a superuser-only ALTER ROLE.
do $$
begin
  if exists(select 1 from pg_roles where rolname='eventra_app' and
    (rolsuper or rolbypassrls or rolcreatedb or rolcreaterole or rolinherit or not rolcanlogin)) then
    raise exception 'eventra_app has unsafe role attributes; operator review required';
  end if;
end $$;
do $$
begin
  if exists (select 1 from pg_auth_members m join pg_roles r on r.oid = m.member where r.rolname = 'eventra_app') then
    raise exception 'eventra_app must not belong to another database role';
  end if;
end $$;
alter role eventra_app set search_path = public, extensions;
grant connect on database postgres to eventra_app;
grant usage on schema app, public, extensions to anon, authenticated, eventra_app;
grant usage on schema auth to eventra_app;
grant execute on function auth.uid() to eventra_app;
-- No password is committed. The operator assigns one interactively after migration.
alter default privileges in schema app revoke all on tables from public, anon, authenticated, eventra_app;
alter default privileges in schema app revoke execute on functions from public;

create function app.touch_updated_at() returns trigger language plpgsql set search_path = '' as $$
begin
  new.updated_at := clock_timestamp();
  return new;
end $$;

create function app.reject_history_change() returns trigger language plpgsql set search_path = '' as $$
begin
  raise exception '% is append-only; create a new version or correction event', tg_table_name using errcode = '23514';
end $$;

create table app.profiles (
  id uuid primary key references auth.users(id) on delete restrict,
  display_name text not null check (char_length(display_name) between 1 and 120),
  phone text check (phone is null or char_length(phone) between 5 and 30),
  avatar_path text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table app.user_roles (
  user_id uuid not null references app.profiles(id) on delete cascade,
  role text not null check (role in ('organizer', 'artist', 'admin')),
  granted_at timestamptz not null default now(),
  primary key (user_id, role)
);

-- Ignore all user-supplied role/admin metadata. New users receive organizer only.
create function app.on_auth_user_created() returns trigger language plpgsql security definer set search_path = '' as $$
begin
  insert into app.profiles (id, display_name)
  values (new.id, left(coalesce(nullif(new.raw_user_meta_data ->> 'display_name', ''), 'New member'), 120));
  insert into app.user_roles (user_id, role) values (new.id, 'organizer');
  return new;
end $$;
create trigger eventra_auth_profile after insert on auth.users for each row execute function app.on_auth_user_created();

create table app.artists (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid references app.profiles(id) on delete restrict,
  slug text not null unique check (slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'),
  name text not null check (char_length(name) between 1 and 120),
  category text not null check (category in ('Live band', 'DJ', 'Vocalist', 'Instrumental')),
  city text not null check (char_length(city) between 1 and 120),
  tagline text not null check (char_length(tagline) between 1 and 180),
  description text not null check (char_length(description) between 1 and 5000),
  tags text[] not null default '{}' check (cardinality(tags) <= 20),
  accent text not null default 'teal' check (accent in ('teal', 'violet', 'amber', 'blue')),
  price_paise bigint not null check (price_paise between 0 and 100000000000),
  currency text not null default 'INR' check (currency = 'INR'),
  rating numeric(2,1) not null default 0 check (rating between 0 and 5),
  review_count integer not null default 0 check (review_count >= 0),
  available boolean not null default false,
  status text not null default 'draft' check (status in ('draft', 'published', 'suspended')),
  home_location extensions.geography(Point,4326),
  is_fixture boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (is_fixture or owner_id is not null)
);
comment on column app.artists.available is 'Preview display flag only. Date-specific availability requires calendar and reservation checks.';
comment on column app.artists.rating is 'Seeded ratings are synthetic. Real review aggregation is a later transaction milestone.';
create index artists_home_location_idx on app.artists using gist(home_location);
create index artists_published_city_category_idx on app.artists(city, category) where status = 'published';
create index artists_owner_idx on app.artists(owner_id);

create table app.artist_embeddings (
  artist_id uuid primary key references app.artists(id) on delete cascade,
  embedding extensions.vector(1024) not null,
  model_name text not null,
  model_digest text not null check (char_length(model_digest) >= 16),
  content_sha256 text not null check (content_sha256 ~ '^[0-9a-f]{64}$'),
  embedded_at timestamptz not null default now()
);
-- No ANN index until corpus size and measured query plans justify its memory cost.

create table app.packages (
  id uuid primary key default gen_random_uuid(),
  artist_id uuid not null references app.artists(id) on delete restrict,
  title text not null check (char_length(title) between 1 and 160),
  description text not null default '' check (char_length(description) <= 5000),
  price_paise bigint not null check (price_paise between 0 and 100000000000),
  currency text not null default 'INR' check (currency = 'INR'),
  duration_minutes integer not null check (duration_minutes between 15 and 1440),
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index packages_artist_idx on app.packages(artist_id);

create table app.availability_windows (
  id uuid primary key default gen_random_uuid(),
  artist_id uuid not null references app.artists(id) on delete restrict,
  during tstzrange not null,
  kind text not null check (kind in ('open', 'blocked')),
  created_at timestamptz not null default now(),
  check (not isempty(during) and not lower_inf(during) and not upper_inf(during) and isfinite(lower(during)) and isfinite(upper(during)) and lower_inc(during) and not upper_inc(during))
);
create index availability_artist_during_idx on app.availability_windows using gist(artist_id, during);

create table app.event_briefs (
  id uuid primary key default gen_random_uuid(),
  organizer_id uuid not null references app.profiles(id) on delete restrict,
  title text not null check (char_length(title) between 1 and 160),
  city text not null,
  venue_location extensions.geography(Point,4326),
  during tstzrange not null,
  event_timezone text not null default 'Asia/Kolkata',
  guest_count integer check (guest_count between 1 and 1000000),
  budget_paise bigint check (budget_paise between 0 and 100000000000),
  notes text not null default '' check (char_length(notes) <= 10000),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (id, organizer_id),
  check (not isempty(during) and not lower_inf(during) and not upper_inf(during) and isfinite(lower(during)) and isfinite(upper(during)) and lower_inc(during) and not upper_inc(during))
);
create index event_briefs_organizer_idx on app.event_briefs(organizer_id);

create function app.validate_event_timezone() returns trigger language plpgsql set search_path = '' as $$
begin
  if not exists (select 1 from pg_catalog.pg_timezone_names where name = new.event_timezone) then
    raise exception 'Unknown event timezone' using errcode = '23514';
  end if;
  return new;
end $$;
create trigger event_brief_timezone before insert or update of event_timezone on app.event_briefs for each row execute function app.validate_event_timezone();

create table app.conversations (
  id uuid primary key default gen_random_uuid(),
  event_id uuid not null,
  artist_id uuid not null references app.artists(id) on delete restrict,
  organizer_id uuid not null,
  created_at timestamptz not null default now(),
  foreign key (event_id, organizer_id) references app.event_briefs(id, organizer_id) on delete restrict,
  unique (event_id, artist_id),
  unique (id, event_id, artist_id, organizer_id)
);
create table app.conversation_members (
  conversation_id uuid not null references app.conversations(id) on delete restrict,
  user_id uuid not null references app.profiles(id) on delete restrict,
  joined_at timestamptz not null default now(),
  primary key (conversation_id, user_id)
);
create index conversation_members_user_idx on app.conversation_members(user_id);

create table app.messages (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  author_id uuid not null,
  client_nonce uuid not null,
  body text not null check (char_length(body) between 1 and 10000),
  created_at timestamptz not null default now(),
  foreign key (conversation_id, author_id) references app.conversation_members(conversation_id, user_id) on delete restrict,
  unique (conversation_id, author_id, client_nonce)
);
create index messages_conversation_created_idx on app.messages(conversation_id, created_at, id);

-- Every quote version is an immutable commercial snapshot, including buffered time.
create table app.quotes (
  id uuid primary key default gen_random_uuid(),
  conversation_id uuid not null,
  event_id uuid not null,
  artist_id uuid not null,
  organizer_id uuid not null,
  version integer not null check (version > 0),
  performance_paise bigint not null check (performance_paise >= 0),
  travel_paise bigint not null default 0 check (travel_paise >= 0),
  equipment_paise bigint not null default 0 check (equipment_paise >= 0),
  tax_paise bigint not null default 0 check (tax_paise >= 0),
  discount_paise bigint not null default 0 check (discount_paise >= 0),
  total_paise bigint not null check (total_paise between 1 and 100000000000),
  currency text not null default 'INR' check (currency = 'INR'),
  performance_during tstzrange not null,
  occupied_during tstzrange not null,
  terms text not null check (char_length(terms) between 1 and 10000),
  created_at timestamptz not null default now(),
  expires_at timestamptz not null,
  foreign key (conversation_id, event_id, artist_id, organizer_id) references app.conversations(id, event_id, artist_id, organizer_id) on delete restrict,
  unique (conversation_id, version),
  unique (id, artist_id, organizer_id),
  check (total_paise::numeric = performance_paise::numeric + travel_paise::numeric + equipment_paise::numeric + tax_paise::numeric - discount_paise::numeric),
  check (expires_at > created_at),
  check (not isempty(performance_during) and not lower_inf(performance_during) and not upper_inf(performance_during) and isfinite(lower(performance_during)) and isfinite(upper(performance_during)) and lower_inc(performance_during) and not upper_inc(performance_during)),
  check (not isempty(occupied_during) and not lower_inf(occupied_during) and not upper_inf(occupied_during) and isfinite(lower(occupied_during)) and isfinite(upper(occupied_during)) and lower_inc(occupied_during) and not upper_inc(occupied_during)),
  check (performance_during <@ occupied_during)
);
create trigger quotes_immutable before update or delete on app.quotes for each row execute function app.reject_history_change();
create index quotes_organizer_idx on app.quotes(organizer_id);
create index quotes_artist_idx on app.quotes(artist_id);

create table app.quote_acceptances (
  quote_id uuid primary key references app.quotes(id) on delete restrict,
  organizer_id uuid not null references app.profiles(id) on delete restrict,
  accepted_at timestamptz not null default now(),
  idempotency_key text not null check (char_length(idempotency_key) between 8 and 120),
  unique (organizer_id, idempotency_key),
  unique (quote_id, organizer_id)
);
create function app.validate_quote_acceptance() returns trigger language plpgsql set search_path = '' as $$
declare q app.quotes;
begin
  select * into strict q from app.quotes where id = new.quote_id;
  if q.organizer_id <> new.organizer_id or q.expires_at <= clock_timestamp() then
    raise exception 'Quote owner mismatch or expired quote' using errcode = '23514';
  end if;
  new.accepted_at := clock_timestamp();
  return new;
end $$;
create trigger quote_acceptance_valid before insert on app.quote_acceptances for each row execute function app.validate_quote_acceptance();
create trigger quote_acceptance_immutable before update or delete on app.quote_acceptances for each row execute function app.reject_history_change();

create table app.reservations (
  id uuid primary key default gen_random_uuid(),
  quote_id uuid not null unique,
  artist_id uuid not null,
  organizer_id uuid not null,
  occupied_during tstzrange not null,
  status text not null default 'held' check (status in ('held', 'confirmed', 'expired', 'released')),
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (quote_id, artist_id, organizer_id) references app.quotes(id, artist_id, organizer_id) on delete restrict,
  foreign key (quote_id, organizer_id) references app.quote_acceptances(quote_id, organizer_id) on delete restrict,
  unique (id, quote_id),
  check (expires_at > created_at),
  check (not isempty(occupied_during) and not lower_inf(occupied_during) and not upper_inf(occupied_during) and isfinite(lower(occupied_during)) and isfinite(upper(occupied_during)) and lower_inc(occupied_during) and not upper_inc(occupied_during)),
  exclude using gist (artist_id with =, occupied_during with &&) where (status in ('held', 'confirmed'))
);
-- Time-based expiry is an explicit worker transition; now() never appears in the predicate.
create index reservations_expiry_idx on app.reservations(expires_at) where status = 'held';
create index reservations_organizer_idx on app.reservations(organizer_id);

create table app.bookings (
  id uuid primary key default gen_random_uuid(),
  reservation_id uuid not null unique,
  quote_id uuid not null unique,
  artist_id uuid not null,
  organizer_id uuid not null,
  total_paise bigint not null check (total_paise between 1 and 100000000000),
  currency text not null default 'INR' check (currency = 'INR'),
  status text not null default 'pending_payment' check (status in ('pending_payment', 'confirmed', 'completed', 'cancelled', 'payment_review')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  foreign key (reservation_id, quote_id) references app.reservations(id, quote_id) on delete restrict,
  foreign key (quote_id, artist_id, organizer_id) references app.quotes(id, artist_id, organizer_id) on delete restrict
);
create index bookings_organizer_idx on app.bookings(organizer_id);
create index bookings_artist_idx on app.bookings(artist_id);

create table app.payment_attempts (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references app.bookings(id) on delete restrict,
  provider text not null default 'local_simulator' check (provider = 'local_simulator'),
  provider_order_id text not null unique,
  idempotency_key text not null unique check (char_length(idempotency_key) between 8 and 120),
  amount_paise bigint not null check (amount_paise between 1 and 100000000000),
  currency text not null default 'INR' check (currency = 'INR'),
  status text not null default 'created' check (status in ('created', 'failed', 'captured', 'requires_review')),
  created_at timestamptz not null default now(),
  unique (id, booking_id, amount_paise, currency)
);
create index payment_attempts_booking_idx on app.payment_attempts(booking_id);

create table app.payments (
  id uuid primary key default gen_random_uuid(),
  attempt_id uuid not null unique,
  booking_id uuid not null,
  amount_paise bigint not null check (amount_paise between 1 and 100000000000),
  currency text not null default 'INR' check (currency = 'INR'),
  provider_event_id text not null unique,
  requires_review boolean not null default false,
  captured_at timestamptz not null default now(),
  foreign key (attempt_id, booking_id, amount_paise, currency) references app.payment_attempts(id, booking_id, amount_paise, currency) on delete restrict
);
create index payments_booking_idx on app.payments(booking_id);
create unique index payments_one_valid_capture_idx on app.payments(booking_id) where (not requires_review);
create trigger payments_immutable before update or delete on app.payments for each row execute function app.reject_history_change();

create table app.refunds (
  id uuid primary key default gen_random_uuid(),
  payment_id uuid not null references app.payments(id) on delete restrict,
  amount_paise bigint not null check (amount_paise between 1 and 100000000000),
  status text not null default 'requested' check (status in ('requested', 'succeeded', 'failed')),
  idempotency_key text not null unique check (char_length(idempotency_key) between 8 and 120),
  provider_event_id text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index refunds_payment_idx on app.refunds(payment_id);

create function app.validate_reservation() returns trigger language plpgsql set search_path = '' as $$
declare q app.quotes;
begin
  if tg_op = 'INSERT' then
    select * into strict q from app.quotes where id = new.quote_id;
    if new.status <> 'held' or new.occupied_during <> q.occupied_during or q.expires_at <= clock_timestamp()
       or new.expires_at <= clock_timestamp() or new.expires_at > q.expires_at
       or new.expires_at > clock_timestamp() + interval '15 minutes' then
      raise exception 'Reservation must hold the exact live quote interval for at most fifteen minutes' using errcode = '23514';
    end if;
  else
    if (new.quote_id, new.artist_id, new.organizer_id, new.occupied_during, new.expires_at, new.created_at)
       is distinct from (old.quote_id, old.artist_id, old.organizer_id, old.occupied_during, old.expires_at, old.created_at) then
      raise exception 'Reservation identity, interval and deadline are immutable' using errcode = '23514';
    end if;
    if new.status <> old.status and not ((old.status = 'held' and new.status in ('confirmed', 'expired', 'released')) or (old.status = 'confirmed' and new.status = 'released')) then
      raise exception 'Illegal reservation transition' using errcode = '23514';
    end if;
    if new.status = 'expired' and old.status <> 'expired' and old.expires_at > clock_timestamp() then
      raise exception 'Cannot expire a live reservation' using errcode = '23514';
    end if;
    if new.status = 'confirmed' and old.status <> 'confirmed' then
      if old.expires_at <= clock_timestamp() or not exists (
        select 1 from app.bookings b join app.payments p on p.booking_id = b.id
        where b.reservation_id = new.id and not p.requires_review and p.amount_paise = b.total_paise
      ) then
        raise exception 'Confirmation requires a live hold and matching reviewed capture' using errcode = '23514';
      end if;
    end if;
  end if;
  return new;
end $$;
create trigger reservations_valid before insert or update on app.reservations for each row execute function app.validate_reservation();

create function app.validate_booking() returns trigger language plpgsql set search_path = '' as $$
declare q app.quotes; r app.reservations;
begin
  select * into strict q from app.quotes where id = new.quote_id;
  select * into strict r from app.reservations where id = new.reservation_id;
  if new.total_paise <> q.total_paise or r.quote_id <> q.id then
    raise exception 'Booking must use the exact immutable quote amount/version' using errcode = '23514';
  end if;
  if tg_op = 'INSERT' and new.status <> 'pending_payment' then
    raise exception 'New booking must await payment' using errcode = '23514';
  end if;
  if tg_op = 'INSERT' and (r.status <> 'held' or r.expires_at <= clock_timestamp()) then
    raise exception 'New booking requires a live held reservation' using errcode = '23514';
  end if;
  if tg_op = 'UPDATE' then
    if (new.reservation_id, new.quote_id, new.artist_id, new.organizer_id, new.total_paise, new.currency, new.created_at)
       is distinct from (old.reservation_id, old.quote_id, old.artist_id, old.organizer_id, old.total_paise, old.currency, old.created_at) then
      raise exception 'Booking commercial snapshot is immutable' using errcode = '23514';
    end if;
    if new.status <> old.status and not (
      (old.status = 'pending_payment' and new.status in ('confirmed', 'cancelled', 'payment_review')) or
      (old.status = 'confirmed' and new.status in ('completed', 'cancelled', 'payment_review')) or
      (old.status = 'payment_review' and new.status in ('cancelled', 'confirmed'))
    ) then
      raise exception 'Illegal booking transition' using errcode = '23514';
    end if;
    if new.status in ('confirmed', 'completed') and (r.status <> 'confirmed' or not exists (
      select 1 from app.payments p where p.booking_id = new.id and not p.requires_review and p.amount_paise = new.total_paise
    )) then
      raise exception 'Booking confirmation requires reserved interval and valid captured amount' using errcode = '23514';
    end if;
    if new.status = 'completed' and upper(q.performance_during) > clock_timestamp() then
      raise exception 'An event cannot complete before its performance ends' using errcode = '23514';
    end if;
  end if;
  return new;
end $$;
create trigger bookings_valid before insert or update on app.bookings for each row execute function app.validate_booking();

create function app.validate_payment_attempt() returns trigger language plpgsql set search_path = '' as $$
begin
  if not exists (select 1 from app.bookings where id = new.booking_id and total_paise = new.amount_paise and currency = new.currency) then
    raise exception 'Payment amount/currency must match booking' using errcode = '23514';
  end if;
  if tg_op = 'UPDATE' and (new.booking_id, new.provider, new.provider_order_id, new.idempotency_key, new.amount_paise, new.currency)
    is distinct from (old.booking_id, old.provider, old.provider_order_id, old.idempotency_key, old.amount_paise, old.currency) then
    raise exception 'Payment attempt commercial identity is immutable' using errcode = '23514';
  end if;
  return new;
end $$;
create trigger payment_attempt_valid before insert or update on app.payment_attempts for each row execute function app.validate_payment_attempt();

create function app.validate_capture() returns trigger language plpgsql set search_path = '' as $$
declare r app.reservations; b app.bookings;
begin
  if current_setting('transaction_isolation') not in ('read committed', 'serializable') then
    raise exception 'Capture transactions require READ COMMITTED or SERIALIZABLE with retry' using errcode = '23514';
  end if;
  select * into strict b from app.bookings where id = new.booking_id;
  select * into strict r from app.reservations where id = b.reservation_id for update;
  -- Persist late/duplicate captures as review records; never revive a hold or booking.
  new.requires_review := new.requires_review or r.status <> 'held' or r.expires_at <= clock_timestamp()
    or b.status <> 'pending_payment' or exists (select 1 from app.payments where booking_id = b.id and not requires_review);
  return new;
end $$;
create trigger payment_capture_valid before insert on app.payments for each row execute function app.validate_capture();

create function app.validate_refund() returns trigger language plpgsql set search_path = '' as $$
declare captured bigint; reserved numeric;
begin
  -- A pre-existing REPEATABLE READ snapshot could miss a sibling refund even
  -- after taking the parent lock. Require RC (the default) or SERIALIZABLE+retry.
  if current_setting('transaction_isolation') not in ('read committed', 'serializable') then
    raise exception 'Refund transactions require READ COMMITTED or SERIALIZABLE with retry' using errcode = '23514';
  end if;
  if tg_op = 'UPDATE' and (new.payment_id, new.amount_paise, new.idempotency_key, new.created_at)
    is distinct from (old.payment_id, old.amount_paise, old.idempotency_key, old.created_at) then
    raise exception 'Refund identity/amount is immutable' using errcode = '23514';
  end if;
  if tg_op = 'UPDATE' and new.status <> old.status and not (old.status = 'requested' and new.status in ('succeeded', 'failed')) then
    raise exception 'Illegal refund transition' using errcode = '23514';
  end if;
  select amount_paise into strict captured from app.payments where id = new.payment_id for update;
  select coalesce(sum(amount_paise), 0) into reserved from app.refunds
    where payment_id = new.payment_id and status in ('requested', 'succeeded') and id <> new.id;
  if new.status in ('requested', 'succeeded') and reserved + new.amount_paise > captured then
    raise exception 'Refund total exceeds captured amount' using errcode = '23514';
  end if;
  return new;
end $$;
create trigger refunds_valid before insert or update on app.refunds for each row execute function app.validate_refund();

create table app.outbox (
  id uuid primary key default gen_random_uuid(),
  aggregate_type text not null,
  aggregate_id uuid not null,
  event_type text not null,
  payload jsonb not null default '{}' check (jsonb_typeof(payload) = 'object'),
  idempotency_key text not null unique,
  created_at timestamptz not null default now(),
  published_at timestamptz,
  attempts integer not null default 0 check (attempts >= 0)
);
create index outbox_pending_idx on app.outbox(created_at) where published_at is null;

create table app.audit_log (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid references app.profiles(id) on delete restrict,
  action text not null,
  entity_type text not null,
  entity_id uuid not null,
  metadata jsonb not null default '{}' check (jsonb_typeof(metadata) = 'object'),
  created_at timestamptz not null default now()
);
create trigger audit_log_immutable before update or delete on app.audit_log for each row execute function app.reject_history_change();

create table app.ai_runs (
  id uuid primary key default gen_random_uuid(),
  actor_id uuid not null references app.profiles(id) on delete restrict,
  model_name text not null,
  model_digest text not null,
  prompt_sha256 text not null check (prompt_sha256 ~ '^[0-9a-f]{64}$'),
  retrieved_artist_ids uuid[] not null default '{}',
  status text not null check (status in ('queued', 'running', 'completed', 'failed', 'cancelled')),
  latency_ms integer check (latency_ms >= 0),
  created_at timestamptz not null default now()
);

create table app.reviews (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null unique references app.bookings(id) on delete restrict,
  organizer_id uuid not null references app.profiles(id) on delete restrict,
  artist_id uuid not null references app.artists(id) on delete restrict,
  stars smallint not null check (stars between 1 and 5),
  body text not null check (char_length(body) between 1 and 4000),
  moderation_status text not null default 'pending' check (moderation_status in ('pending', 'published', 'hidden')),
  created_at timestamptz not null default now()
);
create function app.validate_review() returns trigger language plpgsql set search_path = '' as $$
begin
  if not exists (select 1 from app.bookings where id = new.booking_id and organizer_id = new.organizer_id and artist_id = new.artist_id and status = 'completed') then
    raise exception 'Review requires a completed booking by this organizer' using errcode = '23514';
  end if;
  return new;
end $$;
create trigger reviews_valid before insert or update on app.reviews for each row execute function app.validate_review();

create table app.disputes (
  id uuid primary key default gen_random_uuid(),
  booking_id uuid not null references app.bookings(id) on delete restrict,
  reporter_id uuid not null references app.profiles(id) on delete restrict,
  reason text not null check (char_length(reason) between 1 and 5000),
  status text not null default 'open' check (status in ('open', 'investigating', 'resolved', 'dismissed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Fixed-path authorization helpers avoid recursive policies. No role comes from user metadata.
create function app.is_admin() returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from app.user_roles where user_id = (select auth.uid()) and role = 'admin');
$$;
create function app.owns_artist(artist uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from app.artists where id = artist and owner_id = (select auth.uid()));
$$;
create function app.is_conversation_member(conversation uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from app.conversation_members where conversation_id = conversation and user_id = (select auth.uid()));
$$;
create function app.can_read_booking(booking uuid) returns boolean language sql stable security definer set search_path = '' as $$
  select exists (select 1 from app.bookings b where b.id = booking and (b.organizer_id = (select auth.uid()) or app.owns_artist(b.artist_id) or app.is_admin()));
$$;
revoke all on all functions in schema app from public, anon, authenticated, eventra_app;
grant execute on function app.is_admin(), app.owns_artist(uuid), app.is_conversation_member(uuid), app.can_read_booking(uuid) to authenticated, eventra_app;

do $$
declare t text;
begin
  foreach t in array array['profiles','user_roles','artists','artist_embeddings','packages','availability_windows','event_briefs','conversations','conversation_members','messages','quotes','quote_acceptances','reservations','bookings','payment_attempts','payments','refunds','outbox','audit_log','ai_runs','reviews','disputes'] loop
    execute format('alter table app.%I enable row level security', t);
    execute format('revoke all on table app.%I from public, anon, authenticated, eventra_app', t);
  end loop;
  foreach t in array array['profiles','artists','packages','event_briefs','reservations','bookings','refunds','disputes'] loop
    execute format('create trigger %I before update on app.%I for each row execute function app.touch_updated_at()', t || '_updated_at', t);
  end loop;
end $$;

create policy profiles_self_read on app.profiles for select to authenticated, eventra_app using (id = (select auth.uid()) or app.is_admin());
create policy roles_self_read on app.user_roles for select to authenticated, eventra_app using (user_id = (select auth.uid()) or app.is_admin());
create policy artists_published_read on app.artists for select to anon, authenticated, eventra_app using (status = 'published');
create policy packages_owner_read on app.packages for select to authenticated, eventra_app using (app.owns_artist(artist_id) or app.is_admin());
create policy availability_owner_read on app.availability_windows for select to authenticated, eventra_app using (app.owns_artist(artist_id) or app.is_admin());
create policy events_owner_read on app.event_briefs for select to authenticated, eventra_app using (organizer_id = (select auth.uid()) or app.is_admin());
create policy conversations_member_read on app.conversations for select to authenticated, eventra_app using (app.is_conversation_member(id) or app.is_admin());
create policy conversation_members_read on app.conversation_members for select to authenticated, eventra_app using (app.is_conversation_member(conversation_id) or app.is_admin());
create policy messages_member_read on app.messages for select to authenticated, eventra_app using (app.is_conversation_member(conversation_id) or app.is_admin());
create policy quotes_participant_read on app.quotes for select to authenticated, eventra_app using (organizer_id = (select auth.uid()) or app.owns_artist(artist_id) or app.is_admin());
create policy acceptances_participant_read on app.quote_acceptances for select to authenticated, eventra_app using (organizer_id = (select auth.uid()) or app.is_admin() or exists (select 1 from app.quotes q where q.id = quote_id));
create policy reservations_participant_read on app.reservations for select to authenticated, eventra_app using (organizer_id = (select auth.uid()) or app.owns_artist(artist_id) or app.is_admin());
create policy bookings_participant_read on app.bookings for select to authenticated, eventra_app using (app.can_read_booking(id));
create policy attempts_participant_read on app.payment_attempts for select to authenticated, eventra_app using (app.can_read_booking(booking_id));
create policy payments_participant_read on app.payments for select to authenticated, eventra_app using (app.can_read_booking(booking_id));
create policy refunds_participant_read on app.refunds for select to authenticated, eventra_app using (exists (select 1 from app.payments p where p.id = payment_id));
create policy audit_admin_read on app.audit_log for select to authenticated, eventra_app using (app.is_admin());
create policy ai_runs_owner_read on app.ai_runs for select to authenticated, eventra_app using (actor_id = (select auth.uid()) or app.is_admin());
create policy reviews_participant_read on app.reviews for select to authenticated, eventra_app using (organizer_id = (select auth.uid()) or app.owns_artist(artist_id) or app.is_admin());
create policy disputes_participant_read on app.disputes for select to authenticated, eventra_app using (reporter_id = (select auth.uid()) or app.can_read_booking(booking_id));
-- Embeddings and outbox have no runtime policy/grant. Worker credentials/policies are a later milestone.

grant select on app.profiles, app.user_roles, app.packages, app.availability_windows, app.event_briefs,
  app.conversations, app.conversation_members, app.messages, app.quotes, app.quote_acceptances,
  app.reservations, app.bookings, app.payment_attempts, app.payments, app.refunds,
  app.audit_log, app.ai_runs, app.reviews, app.disputes to authenticated, eventra_app;
-- Safe column grants make the invoker view useful without exposing owner/location internals.
grant select (id, slug, name, category, city, price_paise, rating, review_count, tagline, description, tags, accent, available, status)
  on app.artists to anon, authenticated, eventra_app;
create view public.artist_catalogue_preview with (security_invoker = true, security_barrier = true) as
  select id, slug, name, category, city, price_paise, rating, review_count, tagline, description, tags, accent, available
  from app.artists where status = 'published';
revoke all on public.artist_catalogue_preview from public, anon, authenticated, eventra_app;
grant select on public.artist_catalogue_preview to anon, authenticated, eventra_app;

-- No Realtime publication and no Storage bucket policies are enabled before authorized
-- messaging/file flows are implemented and cross-user integration tests pass.
commit;

