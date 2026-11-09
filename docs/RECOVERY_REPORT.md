# Eventra recovery checkpoint — 5 November 2026

Status: application connectivity and several verified defects repaired; full product recovery is not yet accepted. This report distinguishes executed checks from remaining work. Existing uncommitted work was retained; no commit, push, deployment, database reset, or persistent test-account creation was performed.

## A. Original problems verified during this recovery

- The configured direct PostgreSQL hostname did not resolve on this workstation even after the Supabase project became healthy. A connected agent integration did not mean that the application was connected.
- Supabase Auth used `http://localhost:3000` and had no allowed redirect URLs, while the application requires `http://127.0.0.1:3000`.
- Supabase's default email templates do not implement the application's token-hash confirmation flow. The current dashboard requires custom SMTP or a plan upgrade to customize them. The user explicitly deferred email setup.
- Saved discovery filtered only the first 200 public catalogue results in the browser. A saved artist outside that slice disappeared from the shortlist.
- Artist detail lookup scanned a maximum of 2,000 catalogue records, allowing a valid published artist to return a false 404.
- A failed or unfinished session check could send a save into guest browser storage instead of the user's account.
- A real artist without a photograph received an illustrative fallback captioned as an artist portfolio.
- Header branding, SVG assets, installable icons and manifest colors used inconsistent identities. The user confirmed that there was no approved design and authorized a new design direction.
- Visual inspection of saved screenshots found joined words in the mobile login headline and adjacent account actions without separation.

## B. Root causes

Connection testing had conflated connector access, provider configuration, and actual application access. Paginated collection reads were reused for identity lookups and saved-item selection. Guest behavior was selected from a missing user without distinguishing unresolved identity from a confirmed guest. Styling and branding evolved in separate passes. Earlier successful tests mostly used fixtures or provider doubles, so they did not establish real email, Storage, or payment acceptance.

## C. Architecture and product direction

Eventra is an artist marketplace for event organizers and performers. Visitors discover published artists and can keep a browser shortlist/draft. Organizers create events, contact artists, negotiate immutable quotes and accept a quote into a limited payment hold. Artists manage profiles, portfolios, availability, conversations and quotes. Administrators moderate users, artists and reviews using database-assigned authority. Payment confirmation belongs to authenticated provider callbacks, never the browser or AI.

Retain Next.js/React/TypeScript, FastAPI/Pydantic/psycopg, Supabase Auth/PostgreSQL/Storage and local Ollama. The browser calls same-origin `/api/v1` routes through port 3000. FastAPI verifies identity with Supabase, derives roles from PostgreSQL, validates requests and calls authorized transactional database functions. The runtime login remains `eventra_app`, without superuser or BYPASSRLS. Browser roles cannot execute `app.marketplace_command`. PostgreSQL is authoritative for account records; guest drafts are explicitly browser-only. Optional AI recommends public artists and cannot mutate bookings or finances.

The saved runtime now uses the dashboard-verified session pooler `aws-0-ap-northeast-1.pooler.supabase.com:5432`, with project-qualified restricted username and TLS certificate verification. Existing credentials were preserved in ignored `.env`. No secrets appear in this report.

Requirements conflict: the October local-first blueprint requires a fully offline Linux/WSL release; later authorized implementation uses managed Supabase and Razorpay test payments. This recovery retains the explicitly requested managed connection. It does not claim the offline release gate, worker runtime, or production operations are complete.

Design direction: warm ivory surfaces, deep teal actions, charcoal type, champagne accents, an editorial performance-led homepage and a task-focused account workspace. The new vector mark combines a lowercase e with a stage-like arch and accent star. Public discovery and account pages share identity, spacing, focus, mobile controls and component treatments. Existing licensed illustrative images retain disclosure. This is an initial implemented direction, not a claim that all screens have received final design approval.

## D. Important files changed in this recovery

| File | Purpose |
|---|---|
| `services/api/app/catalogue.py` | Parameterized ID/slug filtering before pagination; direct detail lookups |
| `services/api/app/main.py` | Validated bounded `artist_ids` query and slug lookup integration |
| `packages/contracts/openapi.json` | Regenerated API schema including the new filter |
| `apps/web/src/components/marketplace.tsx` | Saved-ID queries in bounded batches, session-save guard, truthful image caption, logo and homepage copy |
| `apps/web/src/app/identity.css` | Shared visual system, responsive cards, account action separation and login headline fix |
| `apps/web/src/app/layout.tsx` | Loads shared identity styles |
| `apps/web/public/brand/*` | Matching SVG logo/favicon, PNG install icons, Apple icon, ICO and manifest colors |
| `scripts/connection-diagnostic.py` | Read-only diagnosis with safe error categories; no provider exception or credential output |
| `services/api/tests/test_recovery.py` | Regression checks for saved-ID filtering and uncapped detail lookup |
| `tests/browser/recovery.spec.ts` | Saved persistence and failed-session save regressions |
| `tests/browser/workspace.spec.ts` | More useful element diagnostics for narrow-screen overflow |
| ignored `.env` | Verified session-pooler endpoint; existing restricted credentials retained |

Other modified/untracked files were already present at the initial Git-status inspection. They are not all attributable to this recovery. No unrelated work was reverted.

## E. Database and remote operations

Verified project `kqcevtlhhyxkjnxsjjcz` (EventraHQ) before remote operations. It was resumed during the preceding connection task and subsequently reported ACTIVE_HEALTHY.

- Inspected 27 app tables with RLS, 163 constraints, table/storage policies, runtime role flags and command grants. Portfolio bucket is private, limited to 5 MiB and JPEG/PNG/WebP.
- Read hosted migration history. Its execution timestamps differ from source filenames; the existing mapping in `SUPABASE_VERIFICATION.md` explains the differences, including the runtime connection limit. This is not a complete normalized schema-diff certification. Do not blindly run `db push` or reset.
- Ran the existing hosted transaction workflow assertions successfully. Synthetic identities and records were rolled back, leaving no test records from that transaction.
- Saved Auth Site URL `http://127.0.0.1:3000` and exact redirect `http://127.0.0.1:3000/auth/confirm`; dashboard state confirmed both.
- No new schema migration or RLS change was applied. No existing records were deleted.

Security advisor: leaked-password protection is disabled (WARN). Four internal tables deliberately have RLS with no direct-access policies; do not add permissive policies to silence INFO notices. [Supabase password protection](https://supabase.com/docs/guides/auth/password-security#password-strength-and-leaked-password-protection).

## F. Executed verification

| Check | Result and limits |
|---|---|
| ESLint | Passed before the final CSS/icon-only corrections |
| Production build and TypeScript | Passed; final CSS/icon build recorded in BUILD_STATUS |
| API suite | 112 tests passed with provider doubles; not real email or payment evidence |
| Gateway tests | 2 passed with loopback access; restricted run initially failed with EACCES |
| Isolated PostgreSQL migration/authorization suite | 18 passed; Supabase Auth/Storage scaffolding is substituted |
| Hosted SQL workflow transaction | Passed onboarding, metadata role rejection, moderation, availability, saves, event/inquiry/message/quote, acceptance retry and cross-account isolation; rolled back |
| Desktop/mobile browser subset | 34 cases ultimately passed across initial run and targeted reruns. Initial 5 failures: two ambiguous test selectors, two SVG encoding failures, one category-card overflow. All were corrected and affected cases rerun |
| Connected login browser checks | 2 passed against the real running backend; did not submit account credentials |
| Supabase connection helper | Passed Auth reachability, publishable key, email confirmation setting, restricted DB login, extensions, RLS, private-row isolation, grants and policy definitions |
| Actual gateway HTTP smoke | Artists, session and readiness each returned 200; database mode returned 120 existing labelled sample artists |
| Visual QA | Existing connected desktop/mobile login screenshots inspected; final live browser inspection blocked by Work browser-access settings |

No broad test suite was repeated after it passed without a relevant change. Initial restricted-shell build/API runs failed or stalled; the normal-permission executions supplied the reported passing results. Final layout tweaks after screenshot review have build verification but no new browser screenshot because browser access is disabled.

## G. Remaining acceptance gaps

1. Email delivery and templates: user requested that SMTP remain pending. Configure a chosen email provider in Supabase, then apply `supabase/templates/confirmation.html` and `recovery.html`. Do not disable confirmation or claim real registration/recovery is accepted. Current default templates do not satisfy the app's callback contract.
2. Real authenticated organizer/artist sessions, refresh/logout/recovery, persistence after reload, and cross-account HTTP restrictions have not been completed with controlled accounts.
3. Real Storage owner upload, unauthorized upload/read denial and image delivery remain unverified. SQL policies alone are insufficient.
4. Razorpay sandbox credentials, webhook delivery and real checkout are not configured/accepted. Refunds, reconciliation, expiry scheduling, backups and incident operations remain release work.
5. Full live schema/function/index drift reconciliation and concurrent acceptance from independent connections remain outstanding. Existing migration mapping and sequential tests do not replace these checks.
6. The development catalogue contains 120 previously authorized sample artists. They remain labelled and cannot book; hosted production catalogue queries exclude fixtures. No sample data was deleted. A genuine published artist journey remains necessary.
7. Broad workflow response shapes remain loosely typed in several frontend account components. The OpenAPI contract was refreshed, but full generated frontend workflow types and compile-time end-to-end contract enforcement remain unfinished.
8. The older unused `eventra-workspace.tsx` prototype remains in the repository; active routes use the marketplace/account components. Cleanup and a complete page-by-page design review remain to be completed.
9. The offline worker/Redis/Celery release and broader report features must be reconciled with the current managed-development scope. Recovery is not complete merely because the current application builds.

## H. Run Eventra

PowerShell, from this checkout:

```powershell
cd C:\Users\KRISHNA\.codex\.chatgpt-projects\g-p-6ac9f20adf348191b9eb5b681864a192\eventrahq
npm run dev
```

Open `http://127.0.0.1:3000`. The launcher uses saved root `.env` and starts gateway 3000, Next.js 3001 and FastAPI 8000. Do not launch a second copy while its ports are owned. Stop the owning launcher with Ctrl+C. Ollama is optional for manual discovery; AI requires the qualified local model.

For a clean checkout, install recorded dependencies using `npm ci`, create `services/api/.venv` with Python 3.11+, and install `services/api/requirements.lock.txt`. Keep secrets in ignored `.env`; do not overwrite the working file with `.env.example`. Use `npm run supabase:check` only when verifying a changed connection. Do not rerun bootstrap on the existing migrated project.

Targeted commands for future relevant changes:

```powershell
npm run lint
npm run build
npm test
npm run test:database
Push-Location services/api
.\.venv\Scripts\python.exe -m pytest
Pop-Location
```

Fixture browser runs require the connected launcher to be stopped first. `npm run test:e2e` starts its isolated fixture server; these tests are not provider acceptance. Connected login checks can reuse the standard running server with `$env:EVENTRA_CONNECTED_TESTS='1'` and `npm run test:e2e -- tests/browser/login-connection.spec.ts --grep "connected development"`.
