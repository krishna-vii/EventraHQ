-- Explicit development test dataset. No auth-table inserts, fake captures or reviews.
-- The runner supplies verified Auth account IDs using a transaction-local setting.
begin;
select pg_advisory_xact_lock(hashtextextended('eventrahq-development-seed-v1',0));
do $seed$
declare
 m jsonb := current_setting('eventra.seed_manifest')::jsonb;
 account jsonb; fixture jsonb; owner uuid; admin_id uuid; customer uuid;
 artists uuid[] := '{}'; artist_owners uuid[] := '{}'; customers uuid[] := '{}';
 artist uuid; event_id uuid; conversation uuid; quote uuid;
 seed_id uuid := (m->>'seed_id')::uuid;
 base timestamptz := (m->>'base_date')::timestamptz;
 i integer; j integer; idx integer; starts timestamptz; price bigint;
 categories text[] := array['Live band','DJ','Vocalist','Instrumental'];
 cities text[] := array['Mumbai','Bengaluru','Delhi','Pune','Jaipur'];
 occasions text[] := array['Wedding','Corporate event','Private party','Festival'];
begin
 if m->>'project_ref' <> 'kqcevtlhhyxkjnxsjjcz' or jsonb_array_length(m->'accounts')<>13 or jsonb_array_length(m->'fixtures')<>120 then
   raise exception 'Unexpected development seed target or accounts';
 end if;
 for account in select * from jsonb_array_elements(m->'accounts') loop
   if not exists(select 1 from auth.users where id=(account->>'id')::uuid
     and email=account->>'email' and email_confirmed_at is not null
     and raw_app_meta_data->>'eventra_seed_id'=seed_id::text) then
     raise exception 'Seed accounts must first be created and verified through Supabase Auth Admin';
   end if;
 end loop;
 if exists(select 1 from app.audit_log where action='development.seed.completed' and entity_id=seed_id) then
   return; -- Never duplicate records or overwrite changes made during testing.
 end if;
 if base < now() then raise exception 'Seed base date expired; prepare a fresh unseeded manifest'; end if;
 for account in select * from jsonb_array_elements(m->'accounts') loop
   owner := (account->>'id')::uuid;
   if account->>'kind'='admin' then
     admin_id := owner;
     insert into app.user_roles(user_id,role) values(owner,'admin') on conflict do nothing;
     insert into app.audit_log(actor_id,action,entity_type,entity_id,metadata)
       values(owner,'development.seed.admin_granted','profile',owner,jsonb_build_object('seed_id',seed_id));
   elsif account->>'kind'='customer' then customers:=array_append(customers,owner);
   else artist_owners:=array_append(artist_owners,owner);
   end if;
 end loop;
 if cardinality(customers)<>4 or cardinality(artist_owners)<>8 or admin_id is null then
   raise exception 'Unexpected seed role distribution';
 end if;
 for fixture in select * from jsonb_array_elements(m->'fixtures') loop
   insert into app.artists(id,slug,name,category,city,price_paise,tagline,description,tags,status,is_fixture,event_types)
   values((fixture->>'id')::uuid,fixture->>'slug',fixture->>'name',fixture->>'category',fixture->>'city',
     (fixture->>'price_paise')::bigint,fixture->>'tagline',fixture->>'description',
     array(select jsonb_array_elements_text(fixture->'tags')),'published',true,
     array(select jsonb_array_elements_text(fixture->'event_types')));
 end loop;
 for i in 1..8 loop
   owner:=artist_owners[i];
   perform set_config('request.jwt.claim.sub',owner::text,true);
   artist:=(app.marketplace_command('artist_save',jsonb_build_object(
     'slug','eventra-test-performer-'||i,'name','[TEST] Performer '||i,
     'category',categories[1+(i-1)%4],'city',cities[1+(i-1)%5],
     'price_paise',1500000+i*500000,'tags',jsonb_build_array('Test artist','Acoustic','Hindi'),
     'event_types',to_jsonb(occasions),'tagline','Fictional test performer for the development booking workflow.',
     'description','TEST DATA ONLY. This fictional performer is controlled by a test account. Prices and calendar windows are synthetic; no real artist or performance is offered.')) ->>'id')::uuid;
   artists:=array_append(artists,artist);
   for j in 0..9 loop
     perform app.marketplace_command('availability_add',jsonb_build_object(
       'starts_at',base+make_interval(days=>j*7),'ends_at',base+make_interval(days=>(j+1)*7),'kind','open'));
   end loop;
   perform set_config('request.jwt.claim.sub',admin_id::text,true);
   perform app.marketplace_command('artist_moderate',jsonb_build_object('artist_id',artist,'status','published',
     'reason','Development-only TEST profile; synthetic content explicitly labeled.'));
 end loop;
 for i in 1..4 loop
   perform set_config('request.jwt.claim.sub',customers[i]::text,true);
   for j in 1..8 loop
     perform app.marketplace_command('saved_toggle',jsonb_build_object('artist_id',artists[j],'saved',true));
   end loop;
 end loop;
 for i in 0..59 loop
   idx:=1+i%8; customer:=customers[1+i%4]; artist:=artists[idx]; owner:=artist_owners[idx];
   starts:=base+make_interval(days=>i+1,hours=>12); price:=1500000+idx*500000;
   perform set_config('request.jwt.claim.sub',customer::text,true);
   event_id:=(app.marketplace_command('event_create',jsonb_build_object('title','[TEST] Occasion '||(i+1),
     'city',cities[1+(idx-1)%5],'event_type',occasions[1+i%4],
     'starts_at',starts,'ends_at',starts+interval '3 hours','budget_paise',price*2,'guest_count',40+i*5,
     'notes','Synthetic development event. Do not contact a venue or arrange a real performance.')) ->>'id')::uuid;
   conversation:=(app.marketplace_command('inquiry_create',jsonb_build_object('event_id',event_id,'artist_id',artist,
     'body','[TEST] Could you share a proposed set and quote for this fictional event?')) ->>'id')::uuid;
   for j in 1..3 loop
     perform set_config('request.jwt.claim.sub',case when j%2=1 then owner::text else customer::text end,true);
     perform app.marketplace_command('message_send',jsonb_build_object('conversation_id',conversation,
       'client_nonce',gen_random_uuid(),'body',case j when 1 then '[TEST] Yes. We can discuss a three-hour set.'
       when 2 then '[TEST] Please include equipment and travel in the quote.' else '[TEST] The quote below is for testing only.' end));
   end loop;
   perform set_config('request.jwt.claim.sub',owner::text,true);
   quote:=(app.marketplace_command('quote_create',jsonb_build_object('conversation_id',conversation,
     'performance_paise',price,'travel_paise',150000,'equipment_paise',200000,'tax_paise',0,'discount_paise',0,
     'buffer_minutes',60,'valid_hours',168,'client_nonce',gen_random_uuid(),
     'terms','TEST ONLY: fictional quote. No real performance or payment obligation. Real payment confirmation requires the gateway webhook.')) ->>'id')::uuid;
   if i<8 then
     perform set_config('request.jwt.claim.sub',customer::text,true);
     perform app.marketplace_command('quote_accept',jsonb_build_object('quote_id',quote,'idempotency_key',gen_random_uuid()));
   end if;
 end loop;
 insert into app.audit_log(actor_id,action,entity_type,entity_id,metadata)
 values(admin_id,'development.seed.completed','test_dataset',seed_id,
   jsonb_build_object('fixtures',120,'test_artists',8,'accounts',13,'events',60,'conversations',60,
     'messages',240,'quotes',60,'pending_bookings',8,'payments',0,'reviews',0));
 perform set_config('request.jwt.claim.sub','',true);
end;
$seed$;
commit;
