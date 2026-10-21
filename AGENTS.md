# EventraHQ engineering rules

- Retain Next.js App Router, FastAPI, Supabase Auth/Postgres/Storage and local Ollama. Read nested framework instructions.
- Build a public artist marketplace: warm ivory #F7F6F2, charcoal #151A20, teal #147D72, champagne #BE946B. Use accessible contrast, 16px form controls, visible focus, meaningful empty/error/loading states.
- Fictional seed listings and illustrative photography must be labeled. Never fabricate reviews, verified artists, availability, accounts or payments.
- Authenticate on the server with Supabase; resolve roles from the database. Never accept user IDs, roles or payment status as client authority. Keep runtime DB credentials non-owner and without BYPASSRLS.
- All business writes go through authorized database transactions. Preserve immutable quotes, exclusion constraints, payment idempotency and audit history. No destructive migrations without approval.
- No native mobile code until the complete web acceptance gate passes. No deployment, paid provisioning, pushes or production writes without explicit approval.
- Secrets belong in ignored environment files, never source, browser bundles, logs or chat. Treat synced sources/ in the parent workspace as read-only.
- Track evidence and blockers in docs/BUILD_STATUS.md. Distinguish implemented code, automated tests with doubles, database integration tests and real provider verification.
- Run typecheck, build, API tests, gateway tests and desktop/mobile browser tests after relevant changes. Do not silently remove behavioral coverage when redesigning navigation.
