-- Additive marketplace slice. Apply only to a disposable development project first.
-- Runtime is eventra_app, never an owner or BYPASSRLS role. Browser roles receive no business DML.
begin;
alter table app.profiles add column suspended boolean not null default false;
alter table app.artists add column event_types text[] not null default '{}';
alter table app.event_briefs add column event_type text not null default 'Private party';
alter table app.quotes add column client_nonce uuid;
create unique index quotes_client_nonce_idx on app.quotes(conversation_id,client_nonce) where client_nonce is not null;
create unique index artists_one_owner_idx on app.artists(owner_id) where owner_id is not null and not is_fixture;
create index artists_search_idx on app.artists using gin(to_tsvector('simple',name || ' ' || city || ' ' || tagline));

create table app.saved_artists (
  user_id uuid not null references app.profiles(id), artist_id uuid not null references app.artists(id),
  created_at timestamptz not null default now(), primary key(user_id,artist_id)
);
create table app.portfolio (
  id uuid primary key default gen_random_uuid(), artist_id uuid not null references app.artists(id),
  storage_path text not null unique, content_type text not null check(content_type in ('image/jpeg','image/png','image/webp')),
  created_at timestamptz not null default now()
);
create index portfolio_artist_idx on app.portfolio(artist_id,created_at);
create table app.notifications (
  id uuid primary key default gen_random_uuid(), user_id uuid not null references app.profiles(id),
  title text not null, entity_id uuid not null, read_at timestamptz, created_at timestamptz not null default now()
);
create index notifications_user_idx on app.notifications(user_id,created_at desc);
create table app.order_intents (
  booking_id uuid primary key references app.bookings(id), receipt text not null unique,
  state text not null default 'creating' check(state in ('creating','ready','unknown')),
  created_at timestamptz not null default now()
);
create table app.webhook_events (
  event_id text primary key, body_sha256 text not null, event_type text not null,
  received_at timestamptz not null default now()
);
-- Existing simulator rows are retained; only Razorpay is used by the new API.
alter table app.payment_attempts drop constraint payment_attempts_provider_check;
alter table app.payment_attempts add constraint payment_attempts_provider_check check(provider in ('local_simulator','razorpay'));
alter table app.payments add column provider_payment_id text unique;

alter table app.saved_artists enable row level security;
alter table app.portfolio enable row level security;
alter table app.notifications enable row level security;
alter table app.order_intents enable row level security;
alter table app.webhook_events enable row level security;
revoke all on app.saved_artists,app.portfolio,app.notifications,app.order_intents,app.webhook_events from public,anon,authenticated,eventra_app;
create policy saved_self on app.saved_artists for select to authenticated,eventra_app using(user_id=(select auth.uid()));
create policy notifications_self on app.notifications for select to authenticated,eventra_app using(user_id=(select auth.uid()));
create policy portfolio_read on app.portfolio for select to anon,authenticated,eventra_app using(app.owns_artist(artist_id) or exists(select 1 from app.artists a where a.id=artist_id and a.status='published'));
create policy artists_owner on app.artists for select to authenticated,eventra_app using(owner_id=(select auth.uid()) or app.is_admin());
create policy reviews_public on app.reviews for select to anon,authenticated,eventra_app using(moderation_status='published');
grant select on app.saved_artists,app.portfolio,app.notifications to eventra_app;
grant select(is_fixture,event_types) on app.artists to eventra_app;
grant select(id,artist_id,stars,moderation_status) on app.reviews to anon;
grant select(is_fixture,event_types) on app.artists to anon,authenticated;
grant select(id,artist_id,created_at) on app.portfolio to anon,authenticated;
grant execute on function app.owns_artist(uuid) to anon;

create view public.artist_marketplace with(security_invoker=true,security_barrier=true) as
select a.id,a.slug,a.name,a.category,a.city,a.price_paise,
  coalesce((select round(avg(r.stars),1) from app.reviews r where r.artist_id=a.id and r.moderation_status='published'),0) as rating,
  (select count(*)::integer from app.reviews r where r.artist_id=a.id and r.moderation_status='published') as review_count,
  a.tagline,a.description,a.tags,a.accent,false as available,a.is_fixture,a.event_types,
  (select '/api/v1/media/'||p.id::text from app.portfolio p where p.artist_id=a.id order by p.created_at,p.id limit 1) as photo_path
from app.artists a where a.status='published';
revoke all on public.artist_marketplace from public;
grant select on public.artist_marketplace to anon,authenticated,eventra_app;

create function app.available_artists_on(day date) returns setof uuid language sql stable security definer set search_path='' as $$
  select a.id from app.artists a where a.status='published' and not a.is_fixture
    and exists(select 1 from app.availability_windows w where w.artist_id=a.id and w.kind='open'
      and w.during @> tstzrange(day::timestamp at time zone 'Asia/Kolkata',(day+1)::timestamp at time zone 'Asia/Kolkata','[)'))
    and not exists(select 1 from app.availability_windows w where w.artist_id=a.id and w.kind='blocked'
      and w.during && tstzrange(day::timestamp at time zone 'Asia/Kolkata',(day+1)::timestamp at time zone 'Asia/Kolkata','[)'))
    and not exists(select 1 from app.reservations r where r.artist_id=a.id and (r.status='confirmed' or (r.status='held' and r.expires_at>now()))
      and r.occupied_during && tstzrange(day::timestamp at time zone 'Asia/Kolkata',(day+1)::timestamp at time zone 'Asia/Kolkata','[)'));
$$;
revoke all on function app.available_artists_on(date) from public,anon,authenticated;
grant execute on function app.available_artists_on(date) to eventra_app;

-- Storage is private. Owners may upload only under their own UUID and owned artist UUID.
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('artist-portfolios','artist-portfolios',false,5242880,array['image/jpeg','image/png','image/webp'])
on conflict(id) do nothing;
create function app.can_read_media(path text) returns boolean language sql stable security definer set search_path='' as $$
 select exists(select 1 from app.portfolio p join app.artists a on a.id=p.artist_id where p.storage_path=path and (a.status='published' or a.owner_id=(select auth.uid())));
$$;
revoke all on function app.can_read_media(text) from public;
grant execute on function app.can_read_media(text) to anon,authenticated;
create policy eventra_portfolio_read on storage.objects for select to anon,authenticated using(bucket_id='artist-portfolios' and app.can_read_media(name));
create policy eventra_portfolio_insert on storage.objects for insert to authenticated with check(
 bucket_id='artist-portfolios' and (storage.foldername(name))[1]=(select auth.uid())::text
 and app.owns_artist(((storage.foldername(name))[2])::uuid));
create policy eventra_portfolio_delete on storage.objects for delete to authenticated using(bucket_id='artist-portfolios' and (storage.foldername(name))[1]=(select auth.uid())::text);

-- Small, named commands only. Identity comes from the server-verified JWT subject.
-- SECURITY DEFINER is necessary for atomic cross-party writes. Every command checks
-- ownership/participation explicitly; EXECUTE is granted only to the trusted runtime.
create function app.marketplace_command(action text,p jsonb default '{}') returns jsonb
language plpgsql security definer set search_path='' as $$
declare
 u uuid := auth.uid(); a app.artists; e app.event_briefs; c app.conversations; q app.quotes;
 b app.bookings; r app.reservations; attempt app.payment_attempts; payment app.payments;
 result jsonb; ident uuid; owner uuid; span tstzrange; occupied tstzrange; total bigint; seq integer; admitted boolean;
begin
 if action='artist_details' then
   select * into strict a from app.artists where id=(p->>'artist_id')::uuid and status='published';
   return jsonb_build_object('gallery',coalesce((select jsonb_agg(jsonb_build_object('id',x.id,'path','/api/v1/media/'||x.id)) from app.portfolio x where x.artist_id=a.id),'[]'::jsonb),
    'reviews',coalesce((select jsonb_agg(jsonb_build_object('stars',x.stars,'body',x.body)) from app.reviews x where x.artist_id=a.id and x.moderation_status='published'),'[]'::jsonb),
    'calendar',coalesce((select jsonb_agg(jsonb_build_object('starts_at',lower(x.during),'ends_at',upper(x.during),'kind',x.kind)) from app.availability_windows x where x.artist_id=a.id and upper(x.during)>now()),'[]'::jsonb));
 end if;
 if action='media_path' then
   select jsonb_build_object('path',x.storage_path,'content_type',x.content_type) into strict result
   from app.portfolio x join app.artists ar on ar.id=x.artist_id where x.id=(p->>'media_id')::uuid and (ar.status='published' or ar.owner_id=u);
   return result;
 end if;
 -- Payment provider callbacks are separately authenticated by HMAC in FastAPI.
 if action='payment_capture' then
   if exists(select 1 from app.webhook_events where event_id=p->>'event_id' and body_sha256<>p->>'body_sha256') then
     raise exception 'Webhook identity collision' using errcode='23514';
   end if;
   insert into app.webhook_events(event_id,body_sha256,event_type) values(p->>'event_id',p->>'body_sha256','payment.captured') on conflict do nothing;
   if not found then return jsonb_build_object('duplicate',true); end if;
   select * into strict attempt from app.payment_attempts where provider='razorpay' and provider_order_id=p->>'order_id' for update;
   select * into strict b from app.bookings where id=attempt.booking_id for update;
   if (p->>'amount')::bigint<>b.total_paise or p->>'currency'<>'INR' then raise exception 'Capture amount mismatch' using errcode='23514'; end if;
   if exists(select 1 from app.payments where provider_payment_id=p->>'payment_id') then return jsonb_build_object('duplicate',true); end if;
   insert into app.payments(attempt_id,booking_id,amount_paise,currency,provider_event_id,provider_payment_id)
   values(attempt.id,b.id,b.total_paise,'INR',p->>'event_id',p->>'payment_id') returning * into payment;
   if payment.requires_review then
     update app.bookings set status='payment_review' where id=b.id;
     update app.payment_attempts set status='requires_review' where id=attempt.id;
   else
     update app.reservations set status='confirmed' where id=b.reservation_id;
     update app.bookings set status='confirmed' where id=b.id;
     update app.payment_attempts set status='captured' where id=attempt.id;
   end if;
   insert into app.notifications(user_id,title,entity_id) values(b.organizer_id,case when payment.requires_review then 'Payment received: manual review required' else 'Your booking is confirmed' end,b.id);
   insert into app.notifications(user_id,title,entity_id) select owner_id,'Booking payment update',b.id from app.artists where id=b.artist_id;
   insert into app.audit_log(action,entity_type,entity_id,metadata) values('payment.captured','booking',b.id,jsonb_build_object('requires_review',payment.requires_review));
   return jsonb_build_object('received',true,'requires_review',payment.requires_review);
 end if;
 if u is null or not exists(select 1 from app.profiles where id=u and not suspended) then raise exception 'Unauthorized' using errcode='42501'; end if;
 if action='authorize' then return jsonb_build_object('authorized',true); end if;
 if action='profile' then
   select to_jsonb(x) into result from app.profiles x where id=u;
   return jsonb_build_object('profile',result,'roles',coalesce((select jsonb_agg(role) from app.user_roles where user_id=u),'[]'::jsonb));
 elsif action='profile_save' then
   update app.profiles set display_name=p->>'display_name',phone=p->>'phone' where id=u;
   return jsonb_build_object('saved',true);
 elsif action='saved_list' then
   return jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(x)) from app.saved_artists x where user_id=u),'[]'::jsonb));
 elsif action='saved_toggle' then
   if not exists(select 1 from app.artists where id=(p->>'artist_id')::uuid and status='published' and not is_fixture) then raise exception 'Only published real artists can be saved to accounts'; end if;
   if (p->>'saved')::boolean then insert into app.saved_artists values(u,(p->>'artist_id')::uuid,now()) on conflict do nothing;
   else delete from app.saved_artists where user_id=u and artist_id=(p->>'artist_id')::uuid; end if;
   return jsonb_build_object('saved',(p->>'saved')::boolean);
 elsif action='events_list' then
   return jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(x)) from (select eb.*,lower(during) as starts_at,upper(during) as ends_at from app.event_briefs eb where organizer_id=u order by created_at desc limit 100) x),'[]'::jsonb));
 elsif action='event_create' then
   if (p->>'starts_at')::timestamptz<=now() then raise exception 'Event must be in the future'; end if;
   insert into app.event_briefs(organizer_id,title,city,during,budget_paise,guest_count,notes,event_type)
   values(u,p->>'title',p->>'city',tstzrange((p->>'starts_at')::timestamptz,(p->>'ends_at')::timestamptz,'[)'),(p->>'budget_paise')::bigint,(p->>'guest_count')::integer,p->>'notes',p->>'event_type') returning id into ident;
   return jsonb_build_object('id',ident);
 elsif action='artist_me' then
   select * into a from app.artists where owner_id=u and not is_fixture;
   return jsonb_build_object('artist',case when a.id is null then null else to_jsonb(a) end,
     'gallery',coalesce((select jsonb_agg(jsonb_build_object('id',x.id,'path','/api/v1/media/'||x.id)) from app.portfolio x where artist_id=a.id),'[]'::jsonb),
     'calendar',coalesce((select jsonb_agg(jsonb_build_object('id',x.id,'starts_at',lower(x.during),'ends_at',upper(x.during),'kind',x.kind)) from app.availability_windows x where artist_id=a.id and upper(during)>now()),'[]'::jsonb));
 elsif action='artist_save' then
   perform pg_advisory_xact_lock(hashtextextended(u::text,1));
   select * into a from app.artists where owner_id=u and not is_fixture for update;
   if a.status='suspended' then raise exception 'Suspended artists require administrator review' using errcode='42501'; end if;
   if a.id is null then
     insert into app.artists(owner_id,slug,name,category,city,tagline,description,tags,price_paise,event_types)
     values(u,p->>'slug',p->>'name',p->>'category',p->>'city',p->>'tagline',p->>'description',array(select jsonb_array_elements_text(p->'tags')),(p->>'price_paise')::bigint,array(select jsonb_array_elements_text(p->'event_types'))) returning id into ident;
     insert into app.user_roles(user_id,role) values(u,'artist') on conflict do nothing;
   else
     update app.artists set slug=p->>'slug',name=p->>'name',category=p->>'category',city=p->>'city',tagline=p->>'tagline',description=p->>'description',tags=array(select jsonb_array_elements_text(p->'tags')),price_paise=(p->>'price_paise')::bigint,event_types=array(select jsonb_array_elements_text(p->'event_types')),status='draft' where id=a.id;
     ident:=a.id;
   end if;
   insert into app.audit_log(actor_id,action,entity_type,entity_id) values(u,'artist.submitted','artist',ident);
   return jsonb_build_object('id',ident,'status','draft');
 elsif action in ('availability_add','availability_remove','media_add') then
   select * into strict a from app.artists where owner_id=u and not is_fixture and status<>'suspended' for update;
   if action='availability_add' then
     span:=tstzrange((p->>'starts_at')::timestamptz,(p->>'ends_at')::timestamptz,'[)');
     if p->>'kind'='blocked' and exists(select 1 from app.reservations where artist_id=a.id and (status='confirmed' or (status='held' and expires_at>now())) and occupied_during && span) then raise exception 'Cannot block reserved times'; end if;
     insert into app.availability_windows(artist_id,during,kind) values(a.id,span,p->>'kind') returning id into ident;
   elsif action='availability_remove' then
     delete from app.availability_windows where id=(p->>'window_id')::uuid and artist_id=a.id returning id into ident;
     if ident is null then raise exception 'Calendar window not owned' using errcode='42501'; end if;
   else
     if p->>'path' not like u::text||'/'||a.id::text||'/%' or (select count(*) from app.portfolio where artist_id=a.id)>=10 then raise exception 'Invalid portfolio path or portfolio full'; end if;
     insert into app.portfolio(artist_id,storage_path,content_type) values(a.id,p->>'path',p->>'content_type') returning id into ident;
     update app.artists set status='draft' where id=a.id;
   end if;
   return jsonb_build_object('id',ident);
 elsif action='inquiries_list' then
   return jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(x)) from (select cv.*,ar.name as artist_name,eb.title as event_title,ar.owner_id as artist_owner_id from app.conversations cv join app.artists ar on ar.id=cv.artist_id join app.event_briefs eb on eb.id=cv.event_id where cv.organizer_id=u or ar.owner_id=u order by cv.created_at desc limit 100) x),'[]'::jsonb));
 elsif action='inquiry_create' then
   select * into strict e from app.event_briefs where id=(p->>'event_id')::uuid and organizer_id=u;
   select * into strict a from app.artists where id=(p->>'artist_id')::uuid and status='published' and not is_fixture and owner_id<>u;
   insert into app.conversations(event_id,artist_id,organizer_id) values(e.id,a.id,u) on conflict(event_id,artist_id) do nothing returning id into ident;
   if ident is null then select id into ident from app.conversations where event_id=e.id and artist_id=a.id;
   else
     insert into app.conversation_members values(ident,u,now()),(ident,a.owner_id,now());
     insert into app.messages(conversation_id,author_id,client_nonce,body) values(ident,u,gen_random_uuid(),p->>'body');
     insert into app.notifications(user_id,title,entity_id) values(a.owner_id,'New event inquiry',ident);
   end if;
   return jsonb_build_object('id',ident);
 elsif action in ('conversation','message_send','quote_create') then
   select * into strict c from app.conversations where id=(p->>'conversation_id')::uuid for update;
   if not exists(select 1 from app.conversation_members where conversation_id=c.id and user_id=u) then raise exception 'Not a participant' using errcode='42501'; end if;
   if action='conversation' then
     return jsonb_build_object('conversation',to_jsonb(c),'messages',coalesce((select jsonb_agg(to_jsonb(x)) from (select * from app.messages where conversation_id=c.id order by created_at desc,id desc limit 200) x),'[]'::jsonb),
       'quotes',coalesce((select jsonb_agg(to_jsonb(x)) from (select * from app.quotes where conversation_id=c.id order by version desc) x),'[]'::jsonb));
   elsif action='message_send' then
     insert into app.messages(conversation_id,author_id,client_nonce,body) values(c.id,u,(p->>'client_nonce')::uuid,p->>'body') on conflict do nothing returning id into ident;
     if ident is not null then insert into app.notifications(user_id,title,entity_id) select user_id,'New message',c.id from app.conversation_members where conversation_id=c.id and user_id<>u; end if;
     return jsonb_build_object('sent',true);
   else
     select * into strict a from app.artists where id=c.artist_id and owner_id=u and status='published' and not is_fixture;
     select * into strict e from app.event_briefs where id=c.event_id;
     if lower(e.during)<=now() then raise exception 'Event has already started'; end if;
     select id into ident from app.quotes where conversation_id=c.id and client_nonce=(p->>'client_nonce')::uuid;
     if ident is not null then return jsonb_build_object('id',ident); end if;
     if exists(select 1 from app.bookings where quote_id in(select id from app.quotes where conversation_id=c.id) and status<>'cancelled') then raise exception 'Conversation already has a booking'; end if;
     select coalesce(max(version),0)+1 into seq from app.quotes where conversation_id=c.id;
     total:=(p->>'performance_paise')::bigint+(p->>'travel_paise')::bigint+(p->>'equipment_paise')::bigint+(p->>'tax_paise')::bigint-(p->>'discount_paise')::bigint;
     occupied:=tstzrange(lower(e.during)-make_interval(mins=>(p->>'buffer_minutes')::integer),upper(e.during)+make_interval(mins=>(p->>'buffer_minutes')::integer),'[)');
     insert into app.quotes(conversation_id,event_id,artist_id,organizer_id,version,performance_paise,travel_paise,equipment_paise,tax_paise,discount_paise,total_paise,performance_during,occupied_during,terms,expires_at,client_nonce)
     values(c.id,e.id,a.id,c.organizer_id,seq,(p->>'performance_paise')::bigint,(p->>'travel_paise')::bigint,(p->>'equipment_paise')::bigint,(p->>'tax_paise')::bigint,(p->>'discount_paise')::bigint,total,e.during,occupied,p->>'terms',least(now()+make_interval(hours=>(p->>'valid_hours')::integer),lower(e.during)),(p->>'client_nonce')::uuid) returning id into ident;
     insert into app.notifications(user_id,title,entity_id) values(c.organizer_id,'Your artist sent a quote',c.id);
     return jsonb_build_object('id',ident);
   end if;
 elsif action='quote_accept' then
   select * into strict q from app.quotes where id=(p->>'quote_id')::uuid and organizer_id=u;
   perform 1 from app.conversations where id=q.conversation_id for update;
   perform pg_advisory_xact_lock(hashtextextended(q.artist_id::text,2));
   select * into b from app.bookings where quote_id=q.id;
   if b.id is not null then return to_jsonb(b); end if;
   select * into strict a from app.artists where id=q.artist_id and status='published' and not is_fixture for update;
   if exists(select 1 from app.quotes where conversation_id=q.conversation_id and version>q.version) or q.expires_at<=now() or lower(q.performance_during)<=now() then raise exception 'Quote expired or superseded'; end if;
   if not exists(select 1 from app.availability_windows where artist_id=q.artist_id and kind='open' and during @> q.occupied_during)
      or exists(select 1 from app.availability_windows where artist_id=q.artist_id and kind='blocked' and during && q.occupied_during) then raise exception 'Artist calendar does not cover this event and buffer'; end if;
   update app.reservations set status='expired' where artist_id=q.artist_id and status='held' and expires_at<=now();
   update app.bookings set status='cancelled' where artist_id=q.artist_id and status='pending_payment' and reservation_id in(select id from app.reservations where status='expired');
   insert into app.quote_acceptances(quote_id,organizer_id,idempotency_key) values(q.id,u,p->>'idempotency_key');
   insert into app.reservations(quote_id,artist_id,organizer_id,occupied_during,expires_at) values(q.id,q.artist_id,u,q.occupied_during,least(q.expires_at,clock_timestamp()+interval '15 minutes')) returning * into r;
   insert into app.bookings(reservation_id,quote_id,artist_id,organizer_id,total_paise) values(r.id,q.id,q.artist_id,u,q.total_paise) returning * into b;
   insert into app.audit_log(actor_id,action,entity_type,entity_id) values(u,'quote.accepted','booking',b.id);
   return to_jsonb(b);
 elsif action='bookings_list' then
   return jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(x)) from (select bk.*,ar.name as artist_name,eb.title as event_title,lower(qt.performance_during) as starts_at,upper(qt.performance_during) as ends_at,rv.expires_at,rv.status as reservation_status from app.bookings bk join app.artists ar on ar.id=bk.artist_id join app.quotes qt on qt.id=bk.quote_id join app.event_briefs eb on eb.id=qt.event_id join app.reservations rv on rv.id=bk.reservation_id where bk.organizer_id=u or ar.owner_id=u order by bk.created_at desc limit 100) x),'[]'::jsonb));
 elsif action in ('booking_complete','review_create','checkout_prepare','checkout_bind','checkout_unknown') then
   select * into strict b from app.bookings where id=(p->>'booking_id')::uuid for update;
   select * into strict a from app.artists where id=b.artist_id;
   if action='booking_complete' then
     if b.organizer_id<>u and a.owner_id<>u then raise exception 'Not a booking participant' using errcode='42501'; end if;
     update app.bookings set status='completed' where id=b.id and status='confirmed';
     if not found then raise exception 'Only confirmed past bookings can complete'; end if;
     return jsonb_build_object('completed',true);
   end if;
   if b.organizer_id<>u then raise exception 'Not the customer' using errcode='42501'; end if;
   if action='review_create' then
     insert into app.reviews(booking_id,organizer_id,artist_id,stars,body) values(b.id,u,b.artist_id,(p->>'stars')::integer,p->>'body') returning id into ident;
     return jsonb_build_object('id',ident,'status','pending');
   end if;
   if action='checkout_unknown' then update app.order_intents set state='unknown' where booking_id=b.id and state='creating'; return jsonb_build_object('review',true); end if;
   if action='checkout_bind' then
     if (p->>'amount')::bigint<>b.total_paise or p->>'currency'<>'INR' then raise exception 'Provider order mismatch'; end if;
     insert into app.payment_attempts(booking_id,provider,provider_order_id,idempotency_key,amount_paise) values(b.id,'razorpay',p->>'order_id','razorpay:'||b.id,b.total_paise) returning * into attempt;
     update app.order_intents set state='ready' where booking_id=b.id;
     return to_jsonb(attempt);
   end if;
   select * into strict r from app.reservations where id=b.reservation_id;
   if b.status<>'pending_payment' or r.status<>'held' or r.expires_at<=now() then raise exception 'Payment window expired or booking is not payable'; end if;
   select * into attempt from app.payment_attempts where booking_id=b.id and provider='razorpay';
   if attempt.id is not null then return jsonb_build_object('existing',true,'order_id',attempt.provider_order_id,'amount',b.total_paise,'currency','INR'); end if;
   if exists(select 1 from app.order_intents where booking_id=b.id) then raise exception 'Order creation pending or uncertain; reconcile before retrying'; end if;
   insert into app.order_intents(booking_id,receipt) values(b.id,replace(b.id::text,'-',''));
   return jsonb_build_object('existing',false,'receipt',replace(b.id::text,'-',''),'amount',b.total_paise,'currency','INR');
 elsif action='notifications_list' then
   return jsonb_build_object('items',coalesce((select jsonb_agg(to_jsonb(x)) from (select * from app.notifications where user_id=u order by created_at desc limit 100) x),'[]'::jsonb));
 elsif action='notification_read' then
   update app.notifications set read_at=now() where id=(p->>'notification_id')::uuid and user_id=u;
   return jsonb_build_object('read',true);
 elsif action in ('admin_list','artist_moderate','review_moderate','user_moderate') then
   if not app.is_admin() then raise exception 'Administrator required' using errcode='42501'; end if;
   if action='admin_list' then
     return jsonb_build_object('artists',coalesce((select jsonb_agg(to_jsonb(x)) from (select id,name,city,status,owner_id from app.artists where not is_fixture order by updated_at desc limit 100) x),'[]'::jsonb),
       'users',coalesce((select jsonb_agg(to_jsonb(x)) from (select id,display_name,suspended from app.profiles order by created_at desc limit 100) x),'[]'::jsonb),
       'reviews',coalesce((select jsonb_agg(to_jsonb(x)) from (select * from app.reviews where moderation_status='pending' order by created_at limit 100) x),'[]'::jsonb),
       'bookings',coalesce((select jsonb_agg(to_jsonb(x)) from (select * from app.bookings order by created_at desc limit 100) x),'[]'::jsonb),
       'audit',coalesce((select jsonb_agg(to_jsonb(x)) from (select * from app.audit_log order by created_at desc limit 100) x),'[]'::jsonb));
   elsif action='artist_moderate' then
     ident:=(p->>'artist_id')::uuid;
     update app.artists set status=p->>'status' where id=ident and not is_fixture;
   elsif action='review_moderate' then
     ident:=(p->>'review_id')::uuid;
     update app.reviews set moderation_status=case when p->>'status'='published' then 'published' else 'hidden' end where id=ident;
   else
     ident:=(p->>'user_id')::uuid;
     if ident=u or exists(select 1 from app.user_roles where user_id=ident and role='admin') then raise exception 'Admin accounts require an operator change'; end if;
     update app.profiles set suspended=(p->>'suspended')::boolean where id=ident;
     if (p->>'suspended')::boolean then update app.artists set status='suspended' where owner_id=ident; end if;
   end if;
   insert into app.audit_log(actor_id,action,entity_type,entity_id,metadata) values(u,action,'moderation',ident,jsonb_build_object('reason',p->>'reason'));
   return jsonb_build_object('updated',true);
 end if;
 raise exception 'Unknown command' using errcode='42501';
end;
$$;
revoke all on function app.marketplace_command(text,jsonb) from public,anon,authenticated;
grant execute on function app.marketplace_command(text,jsonb) to eventra_app;
commit;
