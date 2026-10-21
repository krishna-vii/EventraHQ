# Build status — 19 October 2026

In progress. Implemented code is not production-readiness or real-provider acceptance.

## Latest checkpoint: secure development seed command prepared

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
