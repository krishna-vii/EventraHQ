# Deployment preparation — not a release approval

The app remains local. No cloud deployment, paid resource provisioning, production migration or Git push has been performed. Begin with `docs/SUPABASE_SETUP.md` for the currently requested development connection. The acceptance gates in `docs/BUILD_STATUS.md` remain binding.

## Environment ownership

Use `.env.example` for local development. The Node launcher reads root `.env`; a cloud API must receive environment variables through its host's secret manager. Do not copy `.env` into an image or put server settings into `NEXT_PUBLIC_*`.

- Browser/Next: public UI only; proxy `/api/v1/*` to the API while preserving cookies and the browser's exact Origin. A same-origin production proxy has not yet been deployed or verified.
- FastAPI: `APP_ENV=staging` or `production`, `APP_ORIGIN=https://YOUR_WEB_HOST`, `API_HOSTNAME=YOUR_API_HOST`, `ALLOW_MANAGED_SERVICES=true`, restricted `DATABASE_URL`, Supabase URL and publishable key, optional database CA file path.
- Supabase: separate development/staging/production projects and migration history. Only the operator uses an admin database login; runtime is `eventra_app` without ownership or BYPASSRLS. Configure exact HTTPS Site URL/redirect and the supplied email templates separately per project. SMTP delivery and recovery must pass acceptance.
- Payments: only `rzp_test_` keys are currently allowed. `RAZORPAY_KEY_SECRET` and `RAZORPAY_WEBHOOK_SECRET` remain server-only. Live keys intentionally fail configuration pending a separate release review.
- AI: local `INFERENCE_PROVIDER=ollama`; hosted `INFERENCE_PROVIDER=hosted` plus HTTPS `HOSTED_AI_URL`, `HOSTED_AI_KEY`, `HOSTED_AI_MODEL`. Real hosted-provider verification is outstanding. Discovery must work when AI is unavailable.

## Proposed compatible hosts

Next on Vercel, FastAPI on Render/Railway, and Supabase for database/Auth/Storage fit the retained architecture. No host has been provisioned. Production proxy, SSE buffering/timeouts, Secure/HttpOnly cookie behavior, origin and hostname enforcement, storage reads, secret injection and gateway webhooks require a staging verification pass before release. No mobile application code is authorized before web acceptance.

## Checks before release

```powershell
npm run lint
npm run typecheck
npm run build
npm test
npm run test:database
cd services/api
.\.venv\Scripts\python.exe -m pytest -q
```

Run `npm run test:e2e` against the local app, and repeat the real customer/artist journey against configured staging. The database harness uses PostgreSQL WASM with Supabase Auth/Storage scaffolding; it does not establish hosted-service or real payment acceptance.

Liveness: `/api/v1/health/live`. Readiness: `/api/v1/health/ready`; an unconfigured preview returns 503. Readiness does not certify full web acceptance. Logs must omit tokens, secrets, raw messages and prompts. Add shared/edge rate limiting before multiple workers; the current auth limiter is per process.

## Payment and operations blockers

Razorpay order creation and signed `payment.captured` webhook processing are implemented but unverified with real sandbox credentials. A checkout callback is never accepted as payment authority. An order whose creation outcome is unknown needs operator reconciliation against its receipt before retry; a delayed capture after the hold expires is marked for review and must not revive a conflicting reservation. Refund processing, reconciliation tooling, hold-expiration scheduling, outbound notification delivery, backup/restore exercises and incident playbooks remain release work. Do not claim production readiness until these and the documented security/concurrency tests pass.
