# Build status — 27 October 2026

## Frontend editorial rebuild — 5 November 2026

Implemented the new obsidian/ivory frontend across the landing page and shared route/workspace system, with local editorial fonts and monochrome brand assets. Backend, Supabase, contracts and environment files were verified unchanged against the start-of-task hashes. Lint, TypeScript, production build and route/asset HTTP checks passed. Browser visual and interaction acceptance remains pending because local browser use is disabled. See [Frontend rebuild](FRONTEND_REBUILD.md) for scope and remaining checks.

## Recovery checkpoint — 5 November 2026

The application connection is repaired using the dashboard-verified IPv4 session pooler and the existing restricted runtime credentials. Auth and database checks passed; actual gateway discovery/session/readiness returned HTTP 200. The catalogue contains 120 previously authorized labelled samples. Auth Site URL and exact callback now match 127.0.0.1. Custom email templates remain blocked by missing SMTP; the user explicitly requested email setup be documented as pending.

Repaired shortlist truncation, capped profile lookup, guest-saving on session failure, misleading fallback-image caption, shared branding and narrow-screen category layout. Added consistent vector/installed icons and corrected login heading/action spacing after inspecting saved screenshots. Preserved existing uncommitted work. No destructive migration, persistent test records, commit, push or deployment.

Executed checks: 112 API tests, 2 gateway tests, 18 isolated database tests, hosted rollback workflow assertions, 34 fixture browser cases across initial run and targeted reruns, and 2 real-backend login-screen checks passed. ESLint passed before final CSS/icon-only work. Final production build including TypeScript passed after the last CSS/icon changes. Live visual inspection of the final changes remains unavailable because local browser access is disabled in Work settings.

Full recovery is not accepted: real Auth/email, Storage and payment journeys, full schema drift comparison, concurrent hosted acceptance, complete design/contract review and release operations remain outstanding. See [Recovery report](RECOVERY_REPORT.md) for exact changes, evidence, limitations and run commands. Do not repeat completed checks without a relevant change.


In progress. Implemented code is not production-readiness or real-provider acceptance.

## Latest checkpoint: local preview routing repaired and hosted sample catalogue installed

On 27 October, the user reported a service-unavailable message immediately on opening Login. Runtime logs showed `/api/v1/session` and `/api/v1/auth/login` reaching the Next.js server and returning 404, although canonical gateway health checks returned 200. Added a development-only, `APP_ENV=local` rewrite for `/api/v1/:path*` from Next.js back through the canonical gateway. This retains gateway origin checks and backend cookie-write/authorization checks. The production routes manifest contains no rewrites. Both local entry points now return HTTP 200 JSON for session checks; invalid empty login requests reach backend validation (422), foreign origins and cookie writes without the canonical origin remain denied (403), and anonymous private events remain denied (401). Lint, TypeScript, production build, two gateway tests, 110 API tests and 12 desktop/mobile routing/login cases passed. Actual embedded-browser verification was unavailable while browser access was disabled.

The connected EventraHQ development Supabase project is healthy. The read-only setup check passed Auth reachability, the saved publishable key, email confirmation, restricted runtime privileges, all 27 app tables with RLS, private-row isolation and Storage policy definitions. The portfolio bucket is private, allows JPEG/PNG/WebP and has a 5 MiB limit. Existing Auth user count was one and was preserved.

At the user's request, inserted **120 labelled catalogue-only sample artists** into the hosted development database using `scripts/seed-catalogue.sql`, generated from the existing development dataset. Verified 30 artists in each of four categories, 24 in each of five cities, zero unsafe fixture flags, and unchanged zero bookings/payments/reviews. Actual website API discovery returned database mode and 120 artists; city/category filters, pagination and empty search results passed. The isolated PostgreSQL suite now passes 18 checks, including catalogue repeatability and rejection of sample inquiries. No real artist, review, availability or payment is asserted. Full interactive test logins still require Auth Admin access; no Auth tables were modified directly.

Auth dashboard Site URL, callback allowlist and confirmation/recovery templates still require dashboard access. The user agreed to enable browser access and sign in; the browser tool continued to report access disabled at the latest check. The current security advisor additionally reports leaked-password protection disabled (WARN); four internal deny-all RLS tables remain expected INFO notices. No privileges or security settings were weakened. This checkpoint does not claim full Supabase acceptance or deployment readiness.

## Previous checkpoint: customer workspace and event-planning design

Implemented the new design in the existing Next.js marketplace, retaining the ivory, charcoal, teal and champagne identity. Account now has URL-addressable navigation for Overview, Your events, Calendar, Conversations, Bookings, Artist studio, Profile and Notifications; Administration remains conditional on the existing account role. Overview reads actual event, inquiry, booking and notification endpoints. Counts distinguish loading, failure and zero records. Expired payment holds do not create an active-payment reminder. The calendar displays event start dates in the visitor's local time; it does not claim artist availability. Event cards support upcoming/past/all views and search, and link to discovery with city/occasion filters.

The event brief uses three grouped sections and a live date/location/guest/budget summary. Guest drafts and the AI-brief transfer remain available. Client validation catches reversed, past and over-seven-day dates. After a successful event save, a failed inquiry can be retried against the same saved event; a successful submission is disabled to prevent duplicate clicks. An ambiguous network failure before an event ID is received still depends on existing backend behavior; this UI change does not add transaction-level idempotency. No database schema, provider configuration or hosted records changed.

Verification on 27 October: lint, TypeScript and production build passed; **110 API tests** and **2 gateway tests** passed. The fixture browser run passed **36 tests** with two connected-service checks intentionally skipped; those two checks then passed separately against the existing configured backend, for **38 passing browser cases** across desktop and mobile. New checks cover saved-record navigation, calendar selection, error retry, honest empty states, guest privacy, live brief summary, invalid dates, inquiry retry without duplicate events, keyboard navigation and 320–1440 px widths. The initial pass found a narrow navigation/header overflow and a test-clock/server-year mismatch; both were corrected before the final run. Desktop and mobile screenshots were visually inspected for workspace, calendar and planning layouts. Screenshots under `../output/website-design/` use explicitly labelled browser test records, not hosted account data.

The standard local preview is running at `http://127.0.0.1:3000/account`, with the event brief at `/plan`; both returned HTTP 200. Account configuration was checked read-only. Real signup/email, portfolio and payment acceptance remain pending as documented below; no deployment or production-readiness claim is made.

For a repeatable browser fixture run, stop the known development launcher first and run `npm run test:e2e`. Playwright now starts `node scripts/dev.mjs --fixtures`, which disables external database, Auth, hosted AI and payment connections for that process without altering `.env`. If reusing an already-running server, start it explicitly with `npm run dev -- --fixtures`. For connected-service checks, use the standard `npm run dev` server and set `EVENTRA_CONNECTED_TESTS=1`, selecting `tests/browser/login-connection.spec.ts`. Populated workspace scenarios use browser-only response doubles; no test users or transactions are created by this suite.

## Previous checkpoint: secure development seed command prepared

The user requested bulk mock data and working test logins, then chose a secure local setup command when administrative integration access was unavailable. Added `npm run seed:development`, restricted to the approved development project and local environment. It prompts privately for an Auth administrative key and certificate-verified PostgreSQL maintenance URL; neither is retained. It creates 13 confirmed test accounts through Supabase Auth Admin, verifies password login/identity, and saves generated passwords only in ignored `.runtime/mock-logins.json`.

The atomic, repeatable business-data seed prepares 120 catalogue fixtures plus eight interactive `[TEST]` artists, 80 calendar windows, 60 events, 60 conversations, 240 messages, 60 quotes, 32 saves and eight pending-payment bookings. No payments, reviews or fake success states are inserted. Collisions with unrelated accounts stop execution; no existing passwords are changed. Auth partial progress is resumable because the private credential file is retained.

Verification: `npm run seed:development -- --plan` passes without writes; `npm run test:database` passes **17 tests** including the complete seed SQL and idempotent rerun; the Python API/setup/seed suite passes **110 tests**. These tests use isolated PostgreSQL/platform scaffolding and Auth provider doubles. **No bulk data or test Auth accounts have been inserted into hosted Supabase yet, and no usable mock credentials have been generated.** The user must run the interactive command with maintenance access. See [TEST_DATA.md](TEST_DATA.md) for exact steps, account names, credential-file location and limitations. Application code and frontend layout did not change in this slice.

## Previous checkpoint: connected login status and recovery

The running workspace gateway on port 3000 and API on port 8000 both return HTTP 200 with `configured: true` from `/api/v1/session`. Both workspace and Desktop environment files contain the approved Supabase project URL, publishable key, restricted database URL and managed-services opt-in. No credentials needed replacing. The frontend had treated every failed session check as `configured: false`, conflating network/expired-session errors with missing setup.

Updated `useSession` to retain an unknown configuration state on errors, validate the status response, and offer a working retry. Login and Account now share an accurate connection notice. Only an explicit backend `configured: false` shows the setup-required message. The live connected login page displays “Account service connected. You can log in or create an account.”

Verification: `npm run lint`, `npm run typecheck`, and `npm run build` passed. `$env:EVENTRA_CONNECTED_TESTS='1'; npx playwright test tests/browser/login-connection.spec.ts` passed **8 tests in 9.0 seconds**, covering desktop/mobile live connection status, retry after a simulated service outage, expired-session messaging and explicit unconfigured responses. Initial browser checks had an ambiguous alert selector matching Next.js's route announcer; the selector was narrowed to application content and all checks rerun successfully. Live checks only read the real backend; failure scenarios use route doubles. No real user login or email flow is claimed. Desktop/mobile screenshots are under ignored `test-results/*-login-connected.png`; the mobile capture was visually inspected. The connected test is opt-in because the existing general browser suite targets the earlier fixture/unconfigured environment.

The running app was left available at `http://127.0.0.1:3000/login`. The changes were synced to the Desktop source with hash guards and backups. Hosted Auth redirect/email-template settings and real account acceptance remain outstanding as described below.

## Previous checkpoint: authentication response validation

Authentication now validates both provider tokens and a positive integer expiry before setting either cookie. Login, refresh and email verification reject malformed, partial or redirected provider responses with HTTP 503 instead of claiming success. Valid signup responses awaiting email confirmation remain unauthenticated. Cookie values are bounded, access-cookie lifetime is capped at one hour, and hosted cookies require HTTPS. Logout reports provider revocation as unconfirmed when only an expired session's refresh cookie remains; it still clears both local cookies. Server-side revocation in that case remains a release-hardening task.

Added 39 provider-double regression cases in `services/api/tests/test_auth_sessions.py`. Corrected a pre-existing migration test's arbitrary 100-character minimum, which rejected the valid short role-grant/connection-budget migrations; transaction-wrapper assertions remain. `services/api/.venv/Scripts/python.exe -m pytest -q`, run from each repository's `services/api` directory using `./.venv/Scripts/python.exe`, passes **99 tests in both workspace and Desktop**. The restricted runner stalled while Windows initialized the asynchronous event-loop socket; a bounded diagnostic identified that boundary, and the approved normal runner completed both suites.

`node .runtime/check-connected-api.mjs` passed: actual `/api/v1/artists`, `/api/v1/session` and `/api/v1/health/ready` returned HTTP 200 against the installed Supabase database. Discovery correctly returned zero real artists, and the anonymous session reported Auth configured. This is not a signup/payment test. Source files were hash-checked before Desktop synchronization and originals backed up under its ignored `.runtime/auth-sync-*` directory. No frontend code changed; the previous build/browser results below were not rerun or claimed as new evidence.

Hosted Auth settings remain blocked: the available in-app browser visibly shows Supabase's sign-in form, and no Supabase connector tools are exposed in this continuation. Site URL, redirect allowlist, email templates and real account/email/Storage journeys remain unverified. No hosted settings, credentials or database records were changed in this checkpoint.

## Previous checkpoint: hosted database connected

Supabase setup advanced beyond the earlier credential blocker below. The approved EventraHQ development project is now migrated and connected from both workspace and Desktop with a restricted login and certificate-verified TLS. All 27 app tables have RLS; the private portfolio bucket and policies exist. Hosted foundation and rollback workflow SQL passed; zero synthetic users/artists/bookings/payments/messages remain. Actual API discovery/session/readiness smoke checks returned HTTP 200 against Supabase. The updated local database harness passes **16 tests**. No frontend changes were made in this checkpoint, so earlier frontend checks were not repeated.

Security advisor: zero WARN/ERROR findings; four expected INFO notices for internal tables with RLS and no direct-access policies. Auth service accepts the saved publishable key with signup/email confirmation enabled. Dashboard Site URL/redirects/email templates are still unverified, because the accessible browser redirects to sign-in. Real account, Storage HTTP and payment journeys remain pending. See [SUPABASE_VERIFICATION.md](SUPABASE_VERIFICATION.md) for exact hosted migration mapping, tests and remaining work. Do not rerun fresh bootstrap on this installed project.

The sections below retain the earlier build history; references to missing credentials or no hosted SQL execution describe the earlier checkpoint and are superseded by this update.

| Slice | Implemented | Verification and remaining gate |
|---|---|---|
| 1 Public experience | Ivory/teal responsive homepage, performance photography, categories/cities, API filters/sort/pagination, dedicated profiles and saved artists | Production build, lint/typecheck and 18 desktop/mobile browser cases pass. Sample artists/photos labeled; no fabricated reviews. |
| 2 Identity/persistence | Supabase Auth through server cookies, verified identity, profiles/DB roles, onboarding | API tests use provider doubles. Real signup, email, sessions and RLS on managed Supabase still pending. |
| 3 Artist/event management | Artist editing, saved artists, event briefs, portfolio Storage, availability | PostgreSQL lifecycle tests pass. Actual Storage upload/download and cross-account hosted acceptance pending. |
| 4 Marketplace transactions | Inquiries, participant messaging, immutable quotes, atomic holds/bookings, notifications | SQL lifecycle/ownership/conflict checks pass. Independent-connection races and real customer/artist browser journey pending. |
| 5 Payments/AI | Razorpay test orders, verified/idempotent captures, late-capture review, configurable hosted AI | No real gateway sandbox credentials/payment; hosted AI not verified. Provider tests are doubles, never claimed as payments. |
| 6 Admin/deployment | DB-authorized moderation/audit, security boundary, setup/deployment documentation | CI/hosting configuration, staging deployment, operational jobs, reconciliation/refunds, monitoring and restore drills remain unfinished. |

## Supabase first: current checkpoint

The user supplied `https://kqcevtlhhyxkjnxsjjcz.supabase.co` and approved adding the EventraHQ schema to this development project. Root ignored `.env` contains the known project URL and managed-services opt-in, but **no publishable key or database credentials**. No remote schema change, role creation or hosted service verification has occurred.

Added `npm run supabase:setup` (fresh development bootstrap), `supabase:configure` (existing migrated database), and `supabase:check` (read-only diagnostics). Setup uses hidden credential input, binds the database target to the chosen project, verifies TLS, refuses existing EventraHQ schemas and migration collisions, applies all migrations in one transaction, and retains only restricted runtime credentials. It never seeds fictional artists, provisions resources, resets databases or saves the admin URL. Its remote execution is unverified until the operator supplies credentials. Details and dashboard/Auth/email steps: `SUPABASE_SETUP.md`.

Docker is absent; a WSL probe timed out. Managed Supabase keeps application processes local but makes identity/data/storage network-dependent. This is an explicit exception to fully offline local-first operation, not a claim that local Supabase is running.

## Commands and results

Executed from the workspace repository unless stated otherwise:

| Command | Observed result |
|---|---|
| `npm run lint` | Passed |
| `npm run typecheck` | Passed |
| `npm run build` | Passed; 11 Next routes generated, including `/auth/confirm` |
| `npm test` | 2 passed; restricted runner initially blocked loopback with EACCES, rerun outside restriction passed |
| `npm run test:database` | 15 passed (parent suite + 14 subtests); all three migrations and foundation SQL assertions executed |
| `services/api/.venv/Scripts/python.exe -m pytest -q` from `services/api` using `./.venv/...` | 60 passed; includes 12 setup/configuration safeguards; restricted Python execution stalled, normal local runner passed |
| `npm run test:e2e` | 18 passed in 43.8s: 9 desktop and 9 mobile web cases |
| `npm run check:native` | Passed; no native mobile source introduced |
| `npm run supabase:check` | Correctly returned exit 1: missing SUPABASE_PUBLISHABLE_KEY and DATABASE_URL; no connection attempted |

The database harness uses real PostgreSQL WASM with PostGIS/vector/GiST and synthetic platform Auth/Storage scaffolding. It does not validate Supabase HTTP services or hosted permission behavior. Browser coverage verifies public interactions, errors, guest persistence, mobile filters, no overflow, navigation, photos and honest unconfigured services. It does not prove real logged-in booking acceptance. No real Razorpay/hosted AI transaction was attempted.

Screenshots saved under ignored `test-results/`: desktop/mobile first screen, homepage and discovery. Desktop and mobile first-screen captures were visually inspected: readable ivory/charcoal surfaces, teal actions, concise hero, working search and responsive navigation. No reference screenshot was supplied in this chat.

## Required next evidence

1. Finish hosted Auth Site URL, exact redirect allowlist and email templates in an accessible signed-in Supabase dashboard. Database bootstrap, private bucket definitions, restricted role checks and hosted SQL validation are already complete; do not repeat bootstrap.
2. Exercise real customer/artist accounts, persisted events, saved artists, portfolio access and quote lifecycle; test independent concurrent acceptance and identity cleanup.
3. Complete genuine Razorpay test checkout and verified webhook confirmation; test delayed/duplicate captures, failure/reconciliation and refunds.
4. Finish scheduled hold expiry, outbound notifications, distributed rate limits, image validation hardening, CI/production proxy/hosting configuration, backups and release review.
5. Only after complete web acceptance consider native mobile implementation.

No Git metadata exists in the workspace or Desktop copy, so no commit/diff baseline is claimed. Source synchronization uses captured file hashes, excludes dependency folders/secrets/generated runtime files, and preserves unrelated Desktop edits.

## Desktop synchronization verification

64 source/document/asset files were copied or merged into `C:\Users\KRISHNA\OneDrive\Desktop\eventrahq` after checking prior hashes. Existing VS Code settings were preserved; README introduction was merged without replacing the existing remainder. No dependency folder or secret file was copied from the workspace. A missing Desktop `.env` was initialized from the template with only the approved project URL and managed-services opt-in.

The Desktop Python environment independently passed the same 60 API/setup tests. Its `npm run supabase:check` correctly reported missing publishable key/database credentials (exit 1). The user must enter those privately through `npm run supabase:setup` before hosted validation can proceed. Root Node development dependencies added in this iteration require `npm ci` in the Desktop copy before running the new lint/database harness there; the recorded frontend/database/browser results were run in the workspace installation.
