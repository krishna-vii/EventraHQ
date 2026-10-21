# EventraHQ marketplace API

The API now includes Supabase Auth cookie sessions, verified database identity, customer and artist records, events, saved artists, portfolio uploads, availability, inquiries, messages, quotes, booking transactions, Razorpay test orders/signed webhooks, notifications and moderation. Real service acceptance remains outstanding; see `../../docs/BUILD_STATUS.md` and `../../docs/SUPABASE_SETUP.md`. Without configuration, public discovery uses labeled fictional records and private workflows fail closed. AI cannot execute account, booking or payment mutations.

The setup/environment and endpoint notes below originated with the first discovery slice. The current exported contract is available at `/api/v1/openapi.json`; use the implementation and build status for current workflow coverage. Start through root `npm run dev` to load root `.env`; direct uvicorn startup does not load that file automatically.

Use Python 3.11 or newer. From this directory create `.venv`, install `requirements-dev.txt`, then run:

```powershell
.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1
.venv/Scripts/python.exe -m pytest
```

On qualified Linux/WSL the equivalent interpreter is `.venv/bin/python`. The Windows preview is an initial development convenience; it does not qualify the blueprint's WSL/Supabase/Celery release environment. Never use multiple API workers: the inference admission gate in this slice is process-local. Before adding Celery or multiple workers, replace it with the blueprint's shared gate. Configure Ollama itself with `OLLAMA_NO_CLOUD=1`, `OLLAMA_NUM_PARALLEL=1`, `OLLAMA_MAX_LOADED_MODELS=1` and loopback binding. Do not run another inference client concurrently during resource qualification.

Default settings:

```dotenv
APP_ENV=local
APP_ORIGIN=http://127.0.0.1:3000
INFERENCE_BASE_URL=http://127.0.0.1:11434
INFERENCE_MODEL=qwen3.5:4b
# Leave DATABASE_URL unset to explicitly use fictional fixture mode.
# DATABASE_URL=postgresql://eventra_app:<local-password>@127.0.0.1:54322/postgres
```

Settings are loaded from the process environment, not automatically from an `.env` file. The parent development launcher supplies settings. Model URLs accept only HTTP loopback origins with explicit ports; redirects and inherited HTTP proxies are disabled. Database connections accept only loopback PostgreSQL port 54322 without URL options. No cloud inference fallback or automatic model download exists. Model presence is checked against Ollama `/api/tags`; tag presence does not certify model blobs, GPU fit or digest provenance. Pin and record the downloaded model digest during the hardware qualification milestone before making a release claim.

All browser requests use relative `/api/v1/...` through port 3000. No CORS middleware is needed on the canonical origin. Browser `Origin` and HTTP `Host` are checked; a foreign Origin is rejected, and inference requires JSON. This is a loopback public-preview boundary, **not authentication**. Local processes and the local user can access these public records. Do not add private data or write endpoints before local Supabase authentication, verified request identity and per-operation authorization are implemented and tested.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/artists` | `search`, exact `category`, case-insensitive exact `city`, inclusive `max_price_paise`. Returns `{items,total,mode}`. Money remains integer paise. |
| `GET /api/v1/artists/{id}` | Public artist or 404; malformed UUID is 422. |
| `GET /api/v1/health/live` | 200 for this running preview without downstream probes; `phase1_complete:false`. |
| `GET /api/v1/health/ready` | Always 503 and `status:preview` until the full release gate exists. Unconfigured database is explicitly unavailable. |
| `POST /api/v1/assistant/runs` | JSON `{brief,artist_ids?}`; up to 1200 characters / 1600 UTF-8 bytes; at most 8 unique public IDs. Omitted IDs use the first eight public catalogue records. SSE status events, then validated result + done, or error. |
| `GET /api/v1/openapi.json` | Offline machine-readable API contract. Interactive documentation is disabled to avoid a remote CDN dependency. |

When `DATABASE_URL` is set, the API reads only `public.artist_catalogue_preview` using short read-only transactions; an unavailable database returns 503 rather than silently changing data modes. Discovery is bounded to 200 rows and AI evidence to eight rows. There is no semantic retrieval or complete 200-row AI search in this initial slice; select public IDs to focus the assistant. The initial database seed is still fictional. Source mode does not mean real providers or verified availability. POST bodies have an 8 KiB limit across chunks and a five-second upload deadline; an incomplete disconnected request never reaches the model.

Inference allows one active call and two queued calls, with a 30-second queue wait and a 120-second generation ceiling. Queue overflow is HTTP 429; provider/model unavailability before streaming is HTTP 503. After SSE headers have been sent, failures are `event:error`, never fake success. Browser cancellation must abort the request; capacity is released in the generator's cleanup. The local model uses `num_ctx=2048`, `num_predict=512`, structured JSON and no tools or raw token display. Context fit and latency remain qualification work; long or complex briefs may require shortening. Only schema-valid results referencing a subset of the supplied public artist IDs reach the browser. This prevents invented record IDs; it cannot certify every natural-language statement produced by the model.

Implementation references: [Ollama chat](https://docs.ollama.com/api/chat), [structured JSON outputs](https://docs.ollama.com/capabilities/structured-outputs), [FastAPI async testing](https://fastapi.tiangolo.com/advanced/async-tests/). Direct dependency versions were checked against the official Python package registry on 18 October 2026; `requirements.lock.txt` records the resolved environment after installation.
