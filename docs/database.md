# Database architecture and validation

The approved development project `kqcevtlhhyxkjnxsjjcz` is migrated and connected with a restricted runtime login and certificate-verified TLS. Hosted SQL foundation/workflow assertions passed; real Auth account and Storage HTTP acceptance remain pending. See [verification evidence](SUPABASE_VERIFICATION.md) and [setup instructions](SUPABASE_SETUP.md). Do not rerun fresh bootstrap on this installed database.

## Schema and server boundary

Three migrations preserve the foundation and add marketplace workflows plus late-capture review handling. There are 27 app tables with RLS, a safe public discovery projection, private portfolio Storage policies, and named transactional commands. The API validates the access token with Supabase Auth, resolves roles from database records, and uses transaction-local verified identity. User metadata and client role flags never grant authority.

The runtime login is `eventra_app`: non-owner, no superuser, no BYPASSRLS, no role/database creation and no other role memberships. Browser `anon`/`authenticated` roles cannot execute the privileged marketplace command. SECURITY DEFINER commands have fixed search paths and explicitly check ownership, membership or admin authority for each action. A database password remains privileged server infrastructure: do not expose it to browsers.

- Profiles, roles, saved artists, events, availability, inquiries, participant messages, immutable quotes, accepted holds, bookings, payments, notifications and audit records persist in Postgres.
- Atomic quote acceptance checks ownership, current version, expiry and calendar conflicts, then creates a hold and pending booking. GiST exclusion prevents overlapping active reservations.
- Captured payment events must match the server-stored order, amount and currency. Raw webhook signatures are checked before the transaction. Duplicates are idempotent. Late captures require review and cannot revive a reservation after cancellation.
- Reviews require a completed booking and moderation. Fictional fixtures have zero reviews and no proven date availability. Seed data is optional development content, never automatically imported by managed setup.
- The existing refund constraints protect captured totals, but a real refund operations workflow and reconciliation are still outstanding.

## Fully local Docker path

Docker is not installed and WSL qualification has not completed on this machine. Do not claim the local stack is running. After qualifying a Linux/WSL Docker host, install the pinned root dependencies and use the configured Supabase CLI. Keep network publications on loopback:

```bash
docker network create -o com.docker.network.bridge.host_binding_ipv4=127.0.0.1 eventra-local
npm run db:start
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

Inspect every published binding, including IPv6. Stop the known Supabase stack if any service is exposed to the LAN. `supabase/config.toml` requests API/Auth/Storage 54321, Postgres 54322, Studio 54323 and captured email 54324. It is local configuration, not a mechanism for changing hosted dashboard settings.

Apply migrations only to a disposable local database. Assign a strong `eventra_app` password interactively using a PostgreSQL maintenance client (`\password eventra_app` in psql); never commit it. Set root `.env` to local Supabase URL/publishable key and `postgresql://eventra_app:URL_ENCODED_PASSWORD@127.0.0.1:54322/postgres`, with `ALLOW_MANAGED_SERVICES=false`. No admin/service-role key belongs in the application.

`npm run db:reset` is destructive and reserved for an explicitly disposable local database. Do not use it on a managed project. A configured but failed database never silently falls back to fictional fixtures.

## Test evidence and limits

`npm run test:database` executes the actual checked-in SQL on PostgreSQL WASM (PGlite) with PostGIS, vector and btree_gist. It runs the original rollback-based foundation assertions and the marketplace lifecycle/authorization tests. Only the platform-owned Auth and Storage schemas/functions are scaffolded. This is stronger than SQL parsing but does not validate hosted Supabase permissions, HTTP Auth/Storage behavior, email delivery, or races between independent PostgreSQL connections.

`npm run supabase:check` performs read-only checks against configured services and never prints keys, passwords or connection strings. Its exact scope is documented in SUPABASE_SETUP.md. Real account journeys, signed Storage requests, concurrent quote acceptance, late webhook behavior, backup/restore and production operations remain acceptance gates.

For a disposable real local PostgreSQL instance with psql installed, `npm run db:test` executes `supabase/tests/foundation.sql` using a session-only `LOCAL_DB_ADMIN_PASSWORD`. The SQL uses transactions and rollback; do not repurpose it as a production health check. Historical checks appear in `progress.md`; current evidence belongs in `BUILD_STATUS.md`.
