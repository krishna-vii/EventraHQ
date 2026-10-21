-- Disposable DEVELOPMENT database only. All synthetic identities/records roll back.
-- Tests actual SQL authorization/workflows; does NOT claim real Auth or payment success.
begin;
set local statement_timeout='20s';
do $$
declare
 customer uuid:=gen_random_uuid(); artist_user uuid:=gen_random_uuid(); operator_id uuid:=gen_random_uuid(); stranger uuid:=gen_random_uuid();
 artist jsonb; event jsonb; inquiry jsonb; quote jsonb; booking jsonb; reply jsonb;
 starts timestamptz:=now()+interval '4 days'; finishes timestamptz:=now()+interval '4 days 2 hours';
begin
 insert into auth.users(id,email,raw_user_meta_data) values
 (customer,customer||'@example.invalid','{"display_name":"Rollback customer","role":"admin"}'),
 (artist_user,artist_user||'@example.invalid','{"display_name":"Rollback artist"}'),
 (operator_id,operator_id||'@example.invalid','{"display_name":"Rollback operator"}'),
 (stranger,stranger||'@example.invalid','{"display_name":"Rollback stranger"}');
 if exists(select 1 from app.user_roles where user_id=customer and role='admin') then raise exception 'Metadata escalated privileges'; end if;
 insert into app.user_roles(user_id,role) values(operator_id,'admin');
 set local role eventra_app;
 perform set_config('request.jwt.claim.sub',artist_user::text,true);
 artist:=app.marketplace_command('artist_save',jsonb_build_object('name','Rollback test artist','slug','rollback-'||artist_user,'category','DJ','city','Mumbai','tagline','Disposable hosted workflow test','description','Synthetic transaction test; rolled back, never a marketplace listing.','tags',jsonb_build_array('House'),'price_paise',100000,'event_types',jsonb_build_array('Wedding')));
 if artist->>'status'<>'draft' then raise exception 'Onboarding did not create draft'; end if;
 perform app.marketplace_command('availability_add',jsonb_build_object('starts_at',starts-interval '1 day','ends_at',finishes+interval '1 day','kind','open'));
 perform set_config('request.jwt.claim.sub',operator_id::text,true);
 perform app.marketplace_command('artist_moderate',jsonb_build_object('artist_id',artist->>'id','status','published','reason','Rollback test only'));
 perform set_config('request.jwt.claim.sub',customer::text,true);
 perform app.marketplace_command('saved_toggle',jsonb_build_object('artist_id',artist->>'id','saved',true));
 event:=app.marketplace_command('event_create',jsonb_build_object('title','Rollback wedding','city','Mumbai','starts_at',starts,'ends_at',finishes,'budget_paise',300000,'guest_count',50,'event_type','Wedding','notes','Rollback test'));
 inquiry:=app.marketplace_command('inquiry_create',jsonb_build_object('event_id',event->>'id','artist_id',artist->>'id','body','Please quote for the test event.'));
 perform set_config('request.jwt.claim.sub',stranger::text,true);
 begin
   perform app.marketplace_command('conversation',jsonb_build_object('conversation_id',inquiry->>'id'));
   raise exception 'Cross-account conversation leak';
 exception when insufficient_privilege then null; end;
 if (select count(*) from app.event_briefs)<>0 then raise exception 'Cross-account RLS leak'; end if;
 perform set_config('request.jwt.claim.sub',artist_user::text,true);
 perform app.marketplace_command('message_send',jsonb_build_object('conversation_id',inquiry->>'id','client_nonce',gen_random_uuid(),'body','Here is the test quote.'));
 quote:=app.marketplace_command('quote_create',jsonb_build_object('conversation_id',inquiry->>'id','client_nonce',gen_random_uuid(),'performance_paise',100000,'travel_paise',10000,'equipment_paise',0,'tax_paise',1000,'discount_paise',0,'terms','Rollback-only test terms','valid_hours',48,'buffer_minutes',60));
 perform set_config('request.jwt.claim.sub',customer::text,true);
 booking:=app.marketplace_command('quote_accept',jsonb_build_object('quote_id',quote->>'id','idempotency_key',gen_random_uuid()));
 if booking->>'status'<>'pending_payment' or (booking->>'total_paise')::bigint<>111000 then raise exception 'Wrong booking state or authoritative price'; end if;
 reply:=app.marketplace_command('quote_accept',jsonb_build_object('quote_id',quote->>'id','idempotency_key',gen_random_uuid()));
 if reply->>'id'<>booking->>'id' then raise exception 'Acceptance retry duplicated booking'; end if;
 if jsonb_array_length(app.marketplace_command('saved_list','{}')->'items')<>1 then raise exception 'Save not persisted within transaction'; end if;
 reset role;
end $$;
rollback;
select 'PASS: hosted onboarding, roles, availability, saved artists, events, inquiries, messaging, immutable quote acceptance and pending booking; all synthetic data rolled back' as result;
