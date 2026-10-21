# Phase 1 implementation record

Historical record of the initial discovery slice. For the current marketplace and Supabase work, use [BUILD_STATUS.md](BUILD_STATUS.md) and [SUPABASE_SETUP.md](SUPABASE_SETUP.md). Statements below describe the earlier snapshot, not current feature coverage.

## Initial slice: 18 October 2026

Implemented and exercised: responsive discovery shell; backend catalogue reads; category, search, city and fee filters; public profile dialogs; browser-local saved shortlist and event draft; same-origin local gateway; model status; bounded backend-only Ollama recommendations; queue and cancellation handling; local error recovery.

Created for the next database gate: Supabase CLI 2.121.0 configuration, PostgreSQL 17 migration with RLS and domain constraints, synthetic seed, transactional SQL assertions, Auth email templates, Caddy and Redis profiles. SQL/PLpgSQL syntax was parsed and the CLI accepted the configuration. These files have not been applied to a running database because Docker is unavailable.

## Observed workstation

| Item | Observed value |
|---|---|
| CPU | AMD Ryzen 7 7435HS, 8 physical cores, 16 logical processors |
| RAM | 25,439,199,232 bytes visible physical memory, approximately 23.69 GiB |
| GPU | NVIDIA RTX 4050 Laptop GPU, 6,141 MiB dedicated VRAM |
| GPU driver | 616.92 |
| Model | Installed qwen3.5:4b, Ollama ID d8b0f5e9760c |
| Local inference sample | Ollama reported 100% GPU placement, 2048 context, approximately 3.1 GB loaded model; GPU total use observed at 4,840 MiB |
| Runtime prerequisites | Docker not found; WSL preflight unqualified (restricted launch failed; elevated status query did not complete) |

This machine is below the blueprint's proposed 32 GiB compact host profile. Initial discovery/inference checks do not qualify simultaneous Supabase, workers and full browser/load tests. The workstation capacity gate must be measured once the complete stack exists; no hardware upgrade is silently assumed.

## Evidence boundaries

The final first-slice checks passed: production Next.js build and TypeScript checks; 28 backend tests; 14 desktop/mobile browser tests including 320/360/390/768/1024/1440px coverage; two gateway tests; and the native-code embargo check. The database files passed static SQL parsing and CLI configuration parsing only. Browser tests used the installed Microsoft Edge engine; they do not establish Firefox, WebKit or physical-device compatibility.

One live inference smoke check returned a valid fictional DJ reference in 5.4 seconds using 2048 context and a maximum 512 output tokens. An earlier check timed out in the queue before the API restart. The recorded successful check is functional evidence only; it does not establish p95 latency, cold-start performance, capacity or sustained stability.

The synthetic smoke result is retained in `docs/evidence/ai-smoke.json`. `docs/models.json` records full installed model digests, parameter sizes and quantization metadata observed during setup. The initial adapter still selects an allowlisted model tag; strict digest admission and complete prompt token budgeting remain release qualification work.

The full release requirements remain open: local Auth and sessions, protected artist management, Storage uploads/policies, participant Realtime, messaging, quote/hold/booking services, payment simulator, workers/outbox dispatch, admin flows, semantic embeddings/LangGraph tools, sustained capacity, offline release rehearsal and database/object restore.

Browser-local drafts are a preview convenience, not durable event records. Fixture availability, fees and ratings are fictional. The current readiness endpoint intentionally reports HTTP 503 and `phase1_complete:false`.

No Phase 1 acceptance sign-off has been created. No cloud deployment or native application source has been created.
