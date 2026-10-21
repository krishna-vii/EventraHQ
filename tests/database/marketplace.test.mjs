import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile, readdir } from 'node:fs/promises';
import { randomUUID } from 'node:crypto';
import { PGlite } from '@electric-sql/pglite';
import { btree_gist } from '@electric-sql/pglite/contrib/btree_gist';
import { postgis } from '@electric-sql/pglite-postgis';
import { vector } from '@electric-sql/pglite-pgvector';

// Actual PostgreSQL WASM + PostGIS/vector/GiST; only Supabase-owned Auth/Storage
// scaffolding is substituted. This is not GoTrue/Storage HTTP or concurrency E2E.
test('marketplace migrations, RLS and transactional lifecycle', {timeout:120000}, async t => {
 const db = new PGlite({extensions:{btree_gist,postgis,vector}});
 t.after(()=>db.close());
 await db.exec(`create role anon; create role authenticated;
 create schema auth; create schema storage;
 create table auth.users(id uuid primary key,email text,raw_user_meta_data jsonb default '{}');
 create function auth.uid() returns uuid language sql stable as $$ select coalesce(nullif(current_setting('request.jwt.claim.sub',true),''),nullif(current_setting('request.jwt.claims',true),'')::jsonb->>'sub')::uuid $$;
 grant usage on schema auth to anon,authenticated; grant execute on function auth.uid() to anon,authenticated;
 create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
 create table storage.objects(id uuid primary key default gen_random_uuid(),bucket_id text,name text);
 alter table storage.objects enable row level security;
 create function storage.foldername(name text) returns text[] language sql immutable as $$ select string_to_array(regexp_replace(name,'/[^/]+$',''),'/') $$;
 `);
 await t.test('all checked-in migrations execute unchanged',async()=>{
  for(const file of (await readdir('supabase/migrations')).filter(f=>f.endsWith('.sql')).sort()) await db.exec(await readFile(`supabase/migrations/${file}`,'utf8'));
 });
 await t.test('original foundation assertions still pass',async()=>{
  const sql=(await readFile('supabase/tests/foundation.sql','utf8')).split('\n').filter(line=>!line.startsWith('\\')).join('\n');
  await db.exec(sql);
 });
 await t.test('hosted rollback workflow script passes without leaving records',async()=>{
  await db.exec(await readFile('supabase/tests/hosted_workflows.sql','utf8'));
  assert.equal((await db.query('select count(*)::int as n from auth.users')).rows[0].n,0);
  assert.equal((await db.query('select count(*)::int as n from app.bookings')).rows[0].n,0);
 });
 const customer=randomUUID(),other=randomUUID(),artistUser=randomUUID(),admin=randomUUID();
 for(const [id,name] of [[customer,'Customer'],[other,'Other customer'],[artistUser,'Artist'],[admin,'Operator']]) await db.query("insert into auth.users(id,email,raw_user_meta_data) values($1,$2,$3::jsonb)",[id,`${id}@example.invalid`,JSON.stringify({display_name:name,role:'admin',is_admin:true})]);
 await db.query("insert into app.user_roles(user_id,role) values($1,'admin')",[admin]);
 async function command(actor,action,p={}) {
  return db.transaction(async tx=>{
   await tx.exec('set local role eventra_app');
   await tx.query("select set_config('request.jwt.claim.sub',$1,true)",[actor||'']);
   return (await tx.query('select app.marketplace_command($1,$2::jsonb) as result',[action,JSON.stringify(p)])).rows[0].result;
  });
 }
 const profile={name:'Integration artist',slug:'integration-artist',category:'DJ',city:'Mumbai',tagline:'Music for your next great occasion',description:'A genuine test record owned by an authenticated synthetic user.',tags:['House'],price_paise:100000,event_types:['Wedding']};
 let artist,event,inquiry,quote,booking,order;
 const starts=new Date(Date.now()+86400000*4),ends=new Date(+starts+7200000);
 const eventData={title:'Contract test wedding',city:'Mumbai',starts_at:starts.toISOString(),ends_at:ends.toISOString(),budget_paise:300000,guest_count:50,event_type:'Wedding',notes:'Integration test preferences'};
 const quoteData={performance_paise:100000,travel_paise:10000,equipment_paise:0,tax_paise:1000,discount_paise:0,terms:'Test terms: setup included. Discuss changes before acceptance.',valid_hours:48,buffer_minutes:60,client_nonce:randomUUID()};
 await t.test('auth metadata cannot promote users; anonymous and non-admin operations fail',async()=>{
  assert.deepEqual((await command(customer,'profile')).roles,['organizer']);
  await assert.rejects(command(null,'events_list'));
  await assert.rejects(command(customer,'admin_list'));
  await assert.rejects(command(customer,'payment_confirmed',{status:'confirmed'}));
 });
 await t.test('artist onboarding creates an owned draft and artist role',async()=>{
  artist=await command(artistUser,'artist_save',profile);
  assert.equal(artist.status,'draft');
  assert.ok((await command(artistUser,'profile')).roles.includes('artist'));
  assert.equal((await db.query('select count(*)::int as n from public.artist_marketplace')).rows[0].n,0);
  await assert.rejects(command(customer,'artist_moderate',{artist_id:artist.id,status:'published',reason:'Not authorized'}));
  await command(admin,'artist_moderate',{artist_id:artist.id,status:'published',reason:'Disposable test verification'});
  assert.equal((await db.query('select rating,review_count from public.artist_marketplace')).rows[0].review_count,0);
 });
 await t.test('private rows obey RLS and browser roles cannot invoke privileged commands',async()=>{
  await db.transaction(async tx=>{
   await tx.exec('set local role eventra_app');
   await tx.query("select set_config('request.jwt.claim.sub',$1,true)",[customer]);
   assert.equal((await tx.query('select count(*)::int as n from app.profiles')).rows[0].n,1);
  });
  await assert.rejects(db.transaction(async tx=>{await tx.exec('set local role authenticated');await tx.query("select app.marketplace_command('admin_list','{}')");}));
 });
 await t.test('saved artists persist per user and cannot mutate another user list',async()=>{
  await command(customer,'saved_toggle',{artist_id:artist.id,saved:true});
  assert.equal((await command(customer,'saved_list')).items.length,1);
  assert.equal((await command(other,'saved_list')).items.length,0);
 });
 await t.test('event inquiry requires event ownership and adds exactly two members',async()=>{
  event=await command(customer,'event_create',eventData);
  await assert.rejects(command(other,'inquiry_create',{event_id:event.id,artist_id:artist.id,body:'Forged inquiry'}));
  inquiry=await command(customer,'inquiry_create',{event_id:event.id,artist_id:artist.id,body:'Please quote for our event.'});
  const duplicate=await command(customer,'inquiry_create',{event_id:event.id,artist_id:artist.id,body:'Retry'});
  assert.equal(duplicate.id,inquiry.id);
  assert.equal((await db.query('select count(*)::int as n from app.conversation_members where conversation_id=$1',[inquiry.id])).rows[0].n,2);
 });
 await t.test('messages are participant-only and retry nonces prevent duplicates',async()=>{
  const p={conversation_id:inquiry.id,client_nonce:randomUUID(),body:'Thanks, happy to discuss.'};
  await assert.rejects(command(other,'conversation',{conversation_id:inquiry.id}));
  await assert.rejects(command(other,'message_send',p));
  await command(artistUser,'message_send',p);await command(artistUser,'message_send',p);
  assert.equal((await command(customer,'conversation',{conversation_id:inquiry.id})).messages.length,2);
 });
 await t.test('quote ownership, pricing snapshot and latest-version acceptance',async()=>{
  await assert.rejects(command(customer,'quote_create',{...quoteData,conversation_id:inquiry.id}));
  quote=await command(artistUser,'quote_create',{...quoteData,conversation_id:inquiry.id});
  const same=await command(artistUser,'quote_create',{...quoteData,conversation_id:inquiry.id});assert.equal(same.id,quote.id);
  await assert.rejects(command(other,'quote_accept',{quote_id:quote.id,idempotency_key:randomUUID()}));
  await assert.rejects(command(customer,'quote_accept',{quote_id:quote.id,idempotency_key:randomUUID()})); // no open calendar
  await command(artistUser,'availability_add',{starts_at:new Date(+starts-86400000).toISOString(),ends_at:new Date(+ends+86400000).toISOString(),kind:'open'});
  const newer=await command(artistUser,'quote_create',{...quoteData,conversation_id:inquiry.id,client_nonce:randomUUID()});
  await assert.rejects(command(customer,'quote_accept',{quote_id:quote.id,idempotency_key:randomUUID()}));
  quote=newer;booking=await command(customer,'quote_accept',{quote_id:quote.id,idempotency_key:randomUUID()});
  assert.equal(booking.total_paise,111000);assert.equal(booking.status,'pending_payment');
  assert.equal((await command(customer,'quote_accept',{quote_id:quote.id,idempotency_key:randomUUID()})).id,booking.id);
 });
 await t.test('overlapping acceptance and blocking a held interval are rejected',async()=>{
  const otherEvent=await command(other,'event_create',eventData);
  const otherInquiry=await command(other,'inquiry_create',{event_id:otherEvent.id,artist_id:artist.id,body:'Second event'});
  const otherQuote=await command(artistUser,'quote_create',{...quoteData,conversation_id:otherInquiry.id,client_nonce:randomUUID()});
  await assert.rejects(command(other,'quote_accept',{quote_id:otherQuote.id,idempotency_key:randomUUID()}));
  await assert.rejects(command(artistUser,'availability_add',{starts_at:starts.toISOString(),ends_at:ends.toISOString(),kind:'blocked'}));
 });
 await t.test('checkout uses booking price and uncertain orders cannot be blindly retried',async()=>{
  await assert.rejects(command(other,'checkout_prepare',{booking_id:booking.id}));
  order=await command(customer,'checkout_prepare',{booking_id:booking.id});assert.equal(order.amount,111000);
  await assert.rejects(command(customer,'checkout_prepare',{booking_id:booking.id}));
  await assert.rejects(command(customer,'checkout_bind',{booking_id:booking.id,order_id:'order_Test123',amount:1,currency:'INR'}));
  await command(customer,'checkout_bind',{booking_id:booking.id,order_id:'order_Test123',amount:order.amount,currency:'INR'});
  assert.equal((await command(customer,'checkout_prepare',{booking_id:booking.id})).existing,true);
 });
 await t.test('only matching captures confirm; duplicate events are idempotent',async()=>{
  const capture={event_id:'evt_Test1',body_sha256:'a'.repeat(64),payment_id:'pay_Test1',order_id:'order_Test123',amount:111000,currency:'INR'};
  await assert.rejects(command(null,'payment_capture',{...capture,amount:1}));
  const result=await command(null,'payment_capture',capture);assert.equal(result.requires_review,false);
  assert.equal((await command(customer,'bookings_list')).items[0].status,'confirmed');
  assert.equal((await command(null,'payment_capture',capture)).duplicate,true);
  await assert.rejects(command(null,'payment_capture',{...capture,body_sha256:'b'.repeat(64)}));
  assert.equal((await db.query('select count(*)::int as n from app.payments')).rows[0].n,1);
 });
 await t.test('future bookings cannot be completed or reviewed and records are immutable',async()=>{
  await assert.rejects(command(customer,'booking_complete',{booking_id:booking.id}));
  await assert.rejects(command(customer,'review_create',{booking_id:booking.id,stars:5,body:'Premature review'}));
  await assert.rejects(db.query('update app.quotes set total_paise=1 where id=$1',[quote.id]));
  await assert.rejects(db.query("update app.audit_log set action='changed'"));
 });
 await t.test('notifications and moderation are persisted and suspensions revoke API authority',async()=>{
  const notices=await command(customer,'notifications_list');assert.ok(notices.items.length>=2);
  await command(customer,'notification_read',{notification_id:notices.items[0].id});
  assert.ok((await command(admin,'admin_list')).audit.length>=3);
  await command(admin,'user_moderate',{user_id:other,suspended:true,reason:'Test suspension enforcement'});
  await assert.rejects(command(other,'authorize'));
  await assert.rejects(command(admin,'user_moderate',{user_id:admin,suspended:true,reason:'Forbidden self suspension'}));
 });
 await t.test('bulk development seed uses real workflow constraints, is repeatable, and never inserts payments or reviews',async()=>{
  const seedId=randomUUID();
  const accounts=[];
  for(const [kind,count] of [['customer',4],['artist',8],['admin',1]]) {
   for(let i=1;i<=count;i++) accounts.push({id:randomUUID(),email:`${kind}${i}@eventrahq.test`,kind});
  }
  const fixtures=Array.from({length:120},(_,i)=>({id:randomUUID(),slug:`seed-test-${i}`,name:`[SAMPLE] Test ${i}`,category:'DJ',city:'Mumbai',price_paise:1000000,tagline:'Fictional test listing',description:'Fictional development artist, not a real performer.',tags:['House'],event_types:['Wedding']}));
  const manifest={project_ref:'kqcevtlhhyxkjnxsjjcz',seed_id:seedId,accounts,fixtures,base_date:new Date(Date.now()+86400000*3).toISOString()};
  const seedSql=(await readFile('scripts/seed-development.sql','utf8')).replace(/\bbegin;/,'').replace(/commit;\s*$/,'');
  const baseline=(await db.query('select (select count(*)::int from app.payments) as payments,(select count(*)::int from app.reviews) as reviews')).rows[0];
  await db.exec('begin;');
  try {
   await db.exec("alter table auth.users add column email_confirmed_at timestamptz; alter table auth.users add column raw_app_meta_data jsonb default '{}';");
   for(const account of accounts) await db.query("insert into auth.users(id,email,email_confirmed_at,raw_app_meta_data) values($1,$2,now(),$3::jsonb)",[account.id,account.email,JSON.stringify({eventra_seed_id:seedId})]);
   await db.query("select set_config('eventra.seed_manifest',$1,true)",[JSON.stringify(manifest)]);
   await db.exec(seedSql);
   const count=async(table,where)=> (await db.query(`select count(*)::int as n from app.${table} where ${where}`)).rows[0].n;
   assert.equal(await count('artists',"slug like 'seed-test-%'"),120);
   assert.equal(await count('artists',"slug like 'eventra-test-performer-%'"),8);
   assert.equal(await count('event_briefs',"title like '[TEST] Occasion %'"),60);
   assert.equal(await count('messages',"body like '[TEST]%'"),240);
   assert.equal(await count('quotes',"terms like 'TEST ONLY:%'"),60);
   assert.equal(await count('bookings',"quote_id in(select id from app.quotes where terms like 'TEST ONLY:%') and status='pending_payment'"),8);
   assert.deepEqual((await db.query('select (select count(*)::int from app.payments) as payments,(select count(*)::int from app.reviews) as reviews')).rows[0],baseline);
   await db.exec(seedSql);
   assert.equal(await count('event_briefs',"title like '[TEST] Occasion %'"),60);
   assert.equal(await count('audit_log',"action='development.seed.completed'"),1);
  } finally { await db.exec('rollback;'); }
 });
});
