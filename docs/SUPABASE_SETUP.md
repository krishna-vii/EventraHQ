# Connect EventraHQ to Supabase development

Status (19 October 2026): the approved development project `https://kqcevtlhhyxkjnxsjjcz.supabase.co` is migrated and connected from both workspace and Desktop. `npm run supabase:check` passes with the restricted runtime login and the official Supabase CA. **Do not rerun fresh bootstrap on this project.** All 27 app tables have RLS, and the private portfolio bucket is configured. Hosted foundation and rollback workflow SQL tests passed with no synthetic records remaining. Actual email confirmation/recovery, Storage HTTP uploads and payment acceptance remain unverified.

The existing root `.env` already contains the runtime configuration; do not paste credentials into chat or replace it with the example. Restart the local application to load it. The setup instructions below are for new environments and the outstanding dashboard settings. The connected integration manages SQL but has no Auth-settings mutation tool; the accessible browser redirected to sign-in, so Site URL, redirect allowlist and email templates have **not** been verified or changed. See `SUPABASE_VERIFICATION.md` for current evidence and migration history.

The web app and API stay on this workstation at `http://127.0.0.1:3000`. Choosing managed Supabase explicitly makes Auth, database and portfolio storage network-dependent; this is not a completely offline workstation deployment. Ollama stays local. Use a separate development project, never production.

## 1. Dashboard settings

Open your existing project in the [Supabase dashboard](https://supabase.com/dashboard).

- Authentication → Providers / Email: enable email sign-up and **Confirm email**. Set minimum password length to 12. Keep anonymous sign-ins disabled.
- Authentication → URL Configuration: Site URL `http://127.0.0.1:3000`; exact Redirect URL `http://127.0.0.1:3000/auth/confirm`. Do not add wildcard redirects. Do not use localhost for one setting and 127.0.0.1 for another.
- Authentication → Email Templates: copy `supabase/templates/confirmation.html` into Confirm signup, and `supabase/templates/recovery.html` into Reset password. They send a token hash to the implemented server exchange; default fragment-token templates are not compatible with this app's cookie session flow.
- Use authorized test inboxes. If the built-in email service restricts recipients or rate-limits delivery, configure your own SMTP before real account acceptance. Do not disable confirmation to make a test pass.
- API Keys: find the **publishable** key (`sb_publishable_…`), or the legacy **anon** key. Do not use a secret/service_role key.
- Connect → Session pooler: copy the PostgreSQL connection string. Port 5432 supports IPv4 without an IPv4 add-on. Copy the exact host; it cannot be inferred from a region name. Supply the project database password and percent-encode reserved password characters. Append `?sslmode=verify-full`.
- Database Settings → SSL: download the root certificate if required for your endpoint and save it locally, for example `.runtime/supabase-ca.crt`. The helper accepts the absolute path. Never resolve certificate failures by turning verification off.

The app schema remains outside the exposed Data API schemas. `public.artist_marketplace` is a safe invoker view; private commands are executable only by the server's restricted PostgreSQL login. Do not expose `app`, grant it broad Data API privileges, or give browser roles permission to execute `marketplace_command`.

## 2. Initialize a fresh development database

From the repository root, after installing Node dependencies and the API virtual environment:

```powershell
npm run supabase:setup
```

Run this in your own interactive terminal. Keys and the administrator connection string are hidden while entered; do not paste them into chat, command arguments, screenshots or source control. The helper:

1. Validates the exact project hostname, publishable-key type and email Auth settings.
2. Asks you to type `development PROJECT_REF` to approve that specific target.
3. Requires a direct or session-pooler admin URL matching the project, with TLS certificate verification.
4. Refuses an existing `app` schema, `eventra_app` login, or colliding migration version. It does not reset a database or overwrite migration history.
5. Applies the checked-in migrations in one transaction, records them in Supabase migration history, and creates a random password for the restricted runtime role.
6. Saves only runtime configuration to the ignored root `.env`, preserving unrelated settings. The administrator connection string is never saved. Keep this file private; Windows uses the containing directory's access controls.
7. Checks Auth, runtime privilege flags, RLS, anonymous private-data isolation, required extensions, command grants, catalogue access and portfolio policy definitions.

No seed data is imported. An empty marketplace is correct until a real artist registers and is moderated. No production database migration or resource provisioning is included.

If migration fails, its transaction rolls back. The error output omits SQL/provider details that could expose credentials. Inspect the database dashboard logs privately for the underlying permission/extension error. Do not weaken runtime privileges as a workaround. A successful database commit followed by a failed connectivity check leaves runtime settings saved; retry the check after resolving connectivity. If the local file cannot be saved after commit, an operator must reset the runtime password and use the configure flow; do not rerun bootstrap blindly.

## 3. Existing installed development database

Do **not** rerun bootstrap over existing data. Review its migration history and the additive migrations first. Back up existing development data before separately applying an outstanding migration with Supabase's migration workflow. Never run `db reset` against a remote project. Existing constraint violations must be investigated, not deleted to force installation.

After an operator has applied the migrations and assigned the restricted role's password, run:

```powershell
npm run supabase:configure
npm run supabase:check
```

The runtime session-pooler username is `eventra_app.PROJECT_REF`, using **that role's password**, not the original postgres password. The runtime direct username is `eventra_app`. Only the setup helper temporarily uses the admin URL. The application refuses owner credentials, superuser and BYPASSRLS roles.

Root `.env` variables are `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `DATABASE_URL`, optional `DATABASE_SSLROOTCERT`, and `ALLOW_MANAGED_SERVICES=true`. No Supabase SDK or database keys need to be added to the browser. Restart `npm run dev` after environment changes; the API does not hot-reload its environment.

## 4. Verify actual Auth, Storage and persistence

`supabase:check` is read-only. Passing it is **not** evidence of successful signup, uploads, email delivery, payment, or every security policy. Complete and record these acceptance steps:

1. Register two distinct accounts with controlled real inboxes. Follow each confirmation email; verify login, refresh, logout, recovery and password change.
2. Save a customer profile and event. Restart the app and verify persistence. The second account must not read or mutate the first account's private data.
3. Onboard an artist with the second account. The new profile is a draft. Upload a JPEG/PNG/WebP ≤5 MiB. Verify the private bucket `artist-portfolios` has the configured limit and MIME allowlist, accepts owner paths, and denies cross-owner writes. Confirm unauthorized draft-media reads fail.
4. Bootstrap an administrator through a separately reviewed maintenance action for a known real account UUID. There is intentionally no public self-promotion endpoint. Log the maintenance role grant; do not use signup metadata for roles.
5. Moderate/publish the artist. Verify discovery, photo reads and genuine availability. Editing a profile/portfolio should require moderation again.
6. Save an artist, create an inquiry, exchange participant-only messages, create a quote, accept it, and verify the pending booking and held interval in the database.
7. Test overlapping acceptance from independent connections. The local WASM harness checks sequential conflicts but is not a concurrent hosted test.
8. Complete the Razorpay test gateway/webhook acceptance separately. Payment controls must remain unavailable until configured. A pending booking is not a confirmed booking.

## Fully local alternative

The current workstation has no Docker installation; local Supabase has not been qualified. Install and qualify Docker/WSL separately before using the local `supabase/config.toml`. Check every published port is bound to loopback before proceeding. Local ports: API/Auth/Storage 54321, PostgreSQL 54322, Studio 54323, captured email 54324; browser gateway 3000, Next 3001, FastAPI 8000, Ollama 11434. The managed bootstrap helper is intentionally restricted to managed development project URLs. For a local instance, apply migrations through the pinned Supabase CLI and configure the runtime role per `docs/database.md`.

## References

- [Supabase connection methods, custom role usernames and SSL](https://supabase.com/docs/guides/database/connecting-to-postgres)
- [Auth email templates](https://supabase.com/docs/guides/auth/auth-email-templates)
- [Supabase Storage access control](https://supabase.com/docs/guides/storage/security/access-control)
- [Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
