-- Keep workstation backend connections bounded. Passwords are operational secrets.
begin;
alter role eventra_app connection limit 8;
commit;
