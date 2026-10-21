# Marketplace implementation

## Audit
The workspace and Desktop copies have matching starting application files. Neither has a .git directory; no Git diff/branch baseline is available. Next 16.4.2 / React 19 / Tailwind 4 / Radix, FastAPI / Pydantic / psycopg, Supabase SQL, and Ollama are retained. Existing functionality is public fixture discovery, browser-only drafts/shortlists and bounded AI. The foundation has 22 tables and protective financial triggers, but no business writes or authentication API. Docker and psql are unavailable. No screenshot was attached to this request; inspect saved and new browser captures.

## Sequential slices
1. Public marketplace: premium design system, homepage, server filters/sort/pagination, dedicated profiles, accessible navigation, mobile drawer, truthful sample data. Verify builds and browser journeys.
2. Persistence and identity: Supabase Auth through server cookies, verified identity, database roles, customer profile and artist application. Runtime credentials cannot bypass RLS. Fail closed without configuration.
3. Artist/event management: saved artists, event briefs, portfolio uploads, calendar and profile editing. Private data persists in Postgres. Guest drafts remain clearly browser-only until saved after login.
4. Transactions: event inquiries and participant messages, immutable quotes, atomic acceptance/holds/bookings, conflict and expired-hold handling, notifications.
5. Providers: Razorpay test orders and signed captured webhooks, idempotency and late-capture review; configurable hosted AI with database-filtered evidence. No simulated checkout success.
6. Administration and deployment: database-derived admin authority, moderation/audit, production templates, CI, health/security headers, deployment and disposable managed database validation instructions.

## Acceptance
An actual customer and artist must register, publish a moderated profile, exchange an inquiry/message/quote, accept, pay through Razorpay test checkout and receive a webhook-confirmed database booking. Automated provider doubles are necessary but insufficient evidence. The development Supabase database is connected and hosted migration/RLS assertions have passed. Full acceptance still requires hosted Auth/email settings, real account and Storage journeys, independent-connection concurrency checks, Razorpay test credentials and the complete payment workflow.

## Latest completed slice
Prepared the user-requested secure local development seed command: Auth Admin test accounts with verified passwords, bulk labeled marketplace data, repeat-run guards, transaction rollback and private credential storage. The full seed SQL passes the database harness (17 tests); the API/setup/seed suite passes 110 tests. Hosted insertion is pending the operator's interactive administrative credential entry. See TEST_DATA.md; no seeded accounts or passwords are claimed yet.

## Previous completed slice: login connection status
Corrected frontend session-status handling: the running backend already reports Supabase configured, but connection/expired-session errors had been mislabeled as missing setup. Login and Account now distinguish these states and provide retry. Lint, typecheck, production build and eight desktop/mobile connection checks pass. This does not establish real-user login/email acceptance.

## Previous completed slice
Hardened Auth provider response validation and truthful logout revocation reporting. Added 39 regression cases; all 99 API/setup tests pass in workspace and Desktop. The connected API discovery/session/readiness smoke check also passes. Hosted Auth dashboard configuration remains pending accessible sign-in. Detailed evidence and limitations are in BUILD_STATUS.md.

## External boundary
The user supplied Supabase project `kqcevtlhhyxkjnxsjjcz` and explicitly authorized its development schema. Through the connected integration, migrations and the restricted runtime login are now installed; hosted SQL assertions and both local connection checks pass. See SUPABASE_VERIFICATION.md. A managed-role compatibility error was corrected in the initial migration before its first successful application. Auth email/redirect settings and real account/Storage/payment journeys remain pending. Razorpay remains unconfigured. Do not deploy, tunnel, purchase, push or write production data without separate approval. Further schema changes use additive migrations with explicit constraint evolution.
