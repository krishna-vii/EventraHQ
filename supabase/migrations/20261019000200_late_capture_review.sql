-- A capture arriving after hold expiry must be retained for operator refund/review,
-- including when a competing acceptance already cancelled the expired booking.
begin;
create or replace function app.validate_booking() returns trigger language plpgsql set search_path='' as $$
declare q app.quotes; r app.reservations;
begin
 select * into strict q from app.quotes where id=new.quote_id;
 select * into strict r from app.reservations where id=new.reservation_id;
 if new.total_paise<>q.total_paise or r.quote_id<>q.id then raise exception 'Booking must use the exact immutable quote amount/version' using errcode='23514'; end if;
 if tg_op='INSERT' and (new.status<>'pending_payment' or r.status<>'held' or r.expires_at<=clock_timestamp()) then raise exception 'New booking requires a live held reservation and pending payment' using errcode='23514'; end if;
 if tg_op='UPDATE' then
  if (new.reservation_id,new.quote_id,new.artist_id,new.organizer_id,new.total_paise,new.currency,new.created_at)
   is distinct from (old.reservation_id,old.quote_id,old.artist_id,old.organizer_id,old.total_paise,old.currency,old.created_at) then raise exception 'Booking commercial snapshot is immutable' using errcode='23514'; end if;
  if new.status<>old.status and not (
   (old.status='pending_payment' and new.status in ('confirmed','cancelled','payment_review')) or
   (old.status='confirmed' and new.status in ('completed','cancelled','payment_review')) or
   (old.status='payment_review' and new.status in ('cancelled','confirmed')) or
   (old.status='cancelled' and new.status='payment_review' and exists(select 1 from app.payments where booking_id=new.id and requires_review))
  ) then raise exception 'Illegal booking transition' using errcode='23514'; end if;
  if new.status in ('confirmed','completed') and (r.status<>'confirmed' or not exists(select 1 from app.payments where booking_id=new.id and not requires_review and amount_paise=new.total_paise)) then raise exception 'Booking confirmation requires reserved interval and valid captured amount' using errcode='23514'; end if;
  if new.status='completed' and upper(q.performance_during)>clock_timestamp() then raise exception 'Event has not ended' using errcode='23514'; end if;
 end if;
 return new;
end;
$$;
commit;
