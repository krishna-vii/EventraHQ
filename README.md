# EventraHQ

EventraHQ is a Next.js/FastAPI artist marketplace in active development. The public experience now includes an ivory/teal responsive homepage, server-filtered discovery and dedicated artist profiles. Backend and UI workflows for Supabase accounts, artist onboarding, events, messages, quotes, bookings and moderation are implemented, with real service acceptance still outstanding.

Without a configured database, discovery uses **eight clearly labeled fictional artists**; guest saved artists and event drafts stay in the browser. Authenticated records use PostgreSQL. Login, uploads and checkout fail visibly when their services are unconfigured. No successful payment or real account journey is claimed yet. See [build evidence](docs/BUILD_STATUS.md).

## Configure Supabase first

Follow [Supabase setup](docs/SUPABASE_SETUP.md). A development project has been identified and approved; credentials must be entered in your own terminal, never chat. For a fresh development database, run `npm run supabase:setup`; for an already migrated database, run `npm run supabase:configure`. Then run `npm run supabase:check` and restart the application. The helper retains only restricted runtime credentials in the ignored root `.env`.

## Run the local preview

From this directory, with the installed dependencies and API environment:

```powershell
npm run dev
```

Open **http://127.0.0.1:3000**. This starts the local gateway, Next.js on 3001 and one FastAPI worker on 8000. Ollama must already be running on 127.0.0.1:11434 to use recommendations; ordinary discovery remains usable without it. Press Ctrl+C in the launcher terminal to stop its owned process trees. Port conflicts fail visibly instead of choosing a different port.

This Windows launcher is a development preview. The release environment defined in the blueprint still requires qualified WSL2/Linux, Docker, Supabase and the worker runtime. Docker is absent and WSL has not passed preflight on this machine: the restricted-shell attempt failed and the elevated status query did not complete. The complete local Phase 1 release gate remains open.

## Install from the recorded dependencies

Use Node.js 22+ and a working Python 3.11+ interpreter. Node 25.8.2 and Python 3.12.14 were used for this initial check. The Windows Store `python` alias on the current machine is unavailable; the already-created API `.venv` is usable, or select an installed interpreter explicitly when recreating it.

```powershell
npm ci
python -m venv services/api/.venv
services/api/.venv/Scripts/python.exe -m pip install -r services/api/requirements.lock.txt
npm run dev
```

On Linux, use `python3` for environment creation and `services/api/.venv/bin/python` for its interpreter. The launcher detects that standard path. If necessary, set `EVENTRA_PYTHON` to the absolute path of the chosen API interpreter. Provisioning downloads packages once; normal application startup uses local assets. No remote font, image or script CDN is required.

Copy `.env.example` to `.env` only when changing settings. The launcher loads the root file. Keep `DATABASE_URL` unset for explicit fictional fixture mode. Once local Supabase is running, the migrations have passed and the `eventra_app` password is assigned, set its local URL to use the database catalogue. A failed configured database returns an error and never silently falls back to fixtures. Never commit `.env` or put backend credentials in public frontend variables.

When copying the project to another folder, exclude `.venv` and `node_modules`, then recreate them from the lockfiles. The project VS Code settings point to `services/api/.venv`; if VS Code has retained another interpreter, run **Python: Select Interpreter** and select that environment. Mixing a Python 3.13 environment with copied Python 3.12 compiled packages causes import failures even when the package folders are present.

The launcher fixes the canonical origin and one API worker. Configure the separately running Ollama daemon with local-only mode, one loaded model and one request lane as described in [API setup](services/api/README.md). The backend also bounds context to 2048 tokens and output to 512. It accepts only the allowlisted `qwen3.5:4b` tag and validates returned artist IDs against the supplied catalogue.

## Project map

| Path | Responsibility |
|---|---|
| `apps/web/` | Next.js App Router, TypeScript, Tailwind 4, Radix dialogs and local brand assets |
| `services/api/` | FastAPI, typed catalogue, protected Ollama adapter and API tests |
| `packages/contracts/openapi.json` | Exported marketplace API contract |
| `supabase/` | Configuration, migrations, optional fictional seed, Auth email templates and SQL assertions |
| `infra/local/` | Caddy release-profile gateway and bounded Redis configuration |
| `scripts/` | Portable preview, local gateway, inventory, build and native-code guard |
| `tests/browser/` | Desktop/mobile browser journeys using installed Microsoft Edge |
| `docs/` | Database setup and implementation progress/evidence |

The portable Node gateway and Caddy are alternative owners of port 3000. Use one at a time. Both preserve API and platform path prefixes. Browsers never contact Ollama, Redis or PostgreSQL directly.

## Checks

```powershell
npm run typecheck
npm run build
npm test
npm run check:native
services/api/.venv/Scripts/python.exe -m pytest services/api/tests
npm run test:e2e
```

The API test command should run from `services/api`, or set its working directory there so `pytest.ini` resolves imports correctly. The browser suite starts the local preview when needed and uses an installed Edge browser. It verifies discovery, shortlists, profile dialogs, event drafts, accessible dialog use, responsive overflow and explicit AI failure behavior. It is desktop/mobile **web** emulation, not native application testing.

`npm run preflight` reports hardware, tools and reserved ports without changing the system. `npm run test:ai` deliberately loads the real local model, requires at least 4 GiB free RAM and saves one smoke result under ignored `.runtime/`. It is separate from ordinary tests because it uses GPU resources. A smoke pass does not replace the blueprint's sustained capacity and AI evaluation gates.

Follow [database setup](docs/database.md) to provision Supabase in the qualified environment. `npm run db:test` runs the plain transaction-based SQL assertions with `psql`; set `LOCAL_DB_ADMIN_PASSWORD` only in the current session. `db:reset` is destructive to the local development database and is reserved for an explicitly disposable fixture dataset.

## Phase gates

The full blueprint is retained in the parent workspace at `../output/local-first/EventraHQ_Local_Development_Blueprint.md`. Implementation is not Phase 1 acceptance. The immediate gate is connecting the approved development Supabase project, executing hosted permission checks, and verifying real customer/artist sessions, portfolio storage and booking persistence. Razorpay sandbox and operating procedures follow before release.

Phase 2 production migration preparation and Phase 3 native/AWS work remain gated. `npm run check:native` rejects native platform source and scaffolding. No native mobile application code has been created.
