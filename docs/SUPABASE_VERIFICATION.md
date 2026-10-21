# Hosted Supabase verification — 19 October 2026

Approved development project: `kqcevtlhhyxkjnxsjjcz` / EventraHQ, active and healthy, PostgreSQL 17, region ap-northeast-1. No project was provisioned and no paid resource or external web deployment was created.

## Completed

- Applied foundation, marketplace workflows and late-capture handling through the connected Supabase integration. Initial role-attribute ALTER failed under managed PostgreSQL; its transaction rolled back. The first unapplied migration was corrected to validate restricted attributes rather than issue a superuser-only ALTER. Security restrictions were preserved.
- Verified 27 app tables, all with RLS; PostGIS, vector and btree_gist installed; browser roles cannot execute the privileged marketplace command.
- Created `eventra_app` as a restricted login, with a random operational password and eight-connection limit. No role membership, superuser, database/role creation, inheritance or BYPASSRLS is granted to runtime. `postgres` may explicitly SET ROLE to this restricted login for maintenance tests; the grant does not run in the opposite direction.
- Stored runtime credentials only in ignored workspace/Desktop environment files. The application never receives postgres/service-role credentials. Password provisioning used a SCRAM verifier; no clear password is committed to SQL/source.
- Downloaded the database root CA from the official URL referenced by Supabase's dashboard source. Only application connections trust that certificate, with `sslmode=verify-full`; system trust and SSL verification were not weakened.
- Created private `artist-portfolios`: maximum 5,242,880 bytes, JPEG/PNG/WebP only. Owner upload/delete and published-or-owner read policies are installed.
- `npm run supabase:check` passed in both workspace and Desktop: Auth settings reachable, saved publishable key accepted, email signup and confirmation enabled, runtime login/privileges, RLS, anonymous profile isolation, command grants, public projection and Storage policy definitions.
- Actual FastAPI routes `/api/v1/artists`, `/api/v1/session` and `/api/v1/health/ready` returned 200 against the hosted database. Discovery reports database mode with zero artists; session reports configured with no logged-in user. These are dependency checks, not real-user acceptance.
- Executed foundation SQL assertions on managed PostgreSQL, including role boundaries, immutable records, reservation/payment/refund invariants and transaction-local identity cleanup. All disposable records rolled back.
- Executed `supabase/tests/hosted_workflows.sql` on managed PostgreSQL: onboarding, moderation, calendar, saved artist, event, inquiry, participant message, quote acceptance, authoritative amount, pending booking, acceptance retry and cross-account isolation. All synthetic identities/records rolled back. No payment gateway was called or payment claimed.
- Supabase security advisor has no WARN/ERROR findings after revoking browser execution of the platform's public RLS event-trigger function. Four INFO findings remain intentionally: RLS with no policies on embeddings, outbox, order intents and webhook events denies direct access; narrowly authorized server functions/maintenance own those operations.

## Hosted migration history

The integration assigns execution timestamps rather than the filenames' original development timestamps. Preserve this mapping. **Do not blindly run CLI db push**: reconcile history using Supabase's reviewed migration-repair workflow before switching migration tools. Do not reapply the same foundation or reset the project.

| Hosted version/name | Repository source / operation |
|---|---|
| 20261019145613 local_foundation | 20261018000100_local_foundation.sql |
| 20261019145623 marketplace_workflows | 20261019000100_marketplace_workflows.sql |
| 20261019145632 late_capture_review | 20261019000200_late_capture_review.sql |
| 20261019145808 configure_restricted_runtime_login | Operational SCRAM password setup and connection limit; password verifier stays out of repository |
| 20261019145836 platform_trigger_permissions | 20261019000300_platform_trigger_permissions.sql |
| 20261019150306 maintenance_role_testing | 20261019000400_maintenance_role_testing.sql |

`20261019000500_runtime_connection_budget.sql` captures the non-secret connection limit for reproducible fresh installations; that setting was already applied by hosted runtime login setup.

## Still required

1. Verify dashboard Site URL `http://127.0.0.1:3000`, exact redirect `/auth/confirm`, minimum password length 12 and the supplied confirmation/recovery HTML. The accessible browser session continued to redirect to sign-in; being connected through the integration did not give it a dashboard session.
2. Real customer and artist sign-up/email verification, refresh/logout, recovery/password change and app-level private-data persistence. No inbox or admin identity was invented; no real account has been created during setup.
3. Real owner upload, cross-owner denial, published-image read and file cleanup through Supabase Storage HTTP. SQL policy existence alone does not validate delivery.
4. Independent concurrent quote acceptance, actual Razorpay sandbox checkout and verified webhook, reconciliation/expiry/refund operations, backups and deployment readiness.

References: [Supabase advisor explanation](https://supabase.com/docs/guides/database/database-linter?lint=0008_rls_enabled_no_policy), [official certificate URL configuration](https://github.com/supabase/supabase/blob/master/apps/studio/hooks/custom-content/custom-content.json), [database TLS guidance](https://supabase.com/docs/guides/database/psql).
