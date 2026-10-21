-- The maintenance administrator may explicitly test runtime RLS via SET ROLE.
-- Direction matters: eventra_app receives no membership or admin privileges.
begin;
grant eventra_app to postgres with inherit false;
commit;
