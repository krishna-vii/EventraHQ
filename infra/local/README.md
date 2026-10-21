# Local supporting services

Run Caddy, Next.js, FastAPI and Ollama on the same WSL2/Linux host. Caddy is the browser entry point at `http://127.0.0.1:3000`; `/api/v1` goes to API `8000`, web routes to Next.js `3001`, and Auth/Storage/Realtime to Supabase `54321`. Path prefixes are preserved. No direct browser route to PostgreSQL, Redis, model inference or PostgREST is configured.

Start Caddy from the project root with `caddy run --config infra/local/Caddyfile`. Validate its syntax with `caddy validate --config infra/local/Caddyfile` before starting. HMR, WebSockets and SSE still require runtime acceptance through port 3000. Caddy's admin port and automatic HTTPS are disabled for this loopback-only profile.

Copy `.env.example` to `.env` here, replace its placeholder with the digest of the selected official Redis image, and use `docker compose --env-file infra/local/.env -f infra/local/compose.yaml up -d`. The file does not download an arbitrary moving tag. Redis's data is limited to 256 MiB inside a 512 MiB container; `noeviction` makes queue exhaustion explicit. Persistent PostgreSQL/outbox records must recover failed queue publication when the worker milestone is implemented.

Stop supporting services with `docker compose --env-file infra/local/.env -f infra/local/compose.yaml stop`; retain named volumes. Never use `down -v` for routine shutdown. Redis is an internal loopback service without an application-facing HTTP port. This workstation profile is unsuitable for LAN exposure.

Before starting Supabase, create a dedicated network with `docker network create -o com.docker.network.bridge.host_binding_ipv4=127.0.0.1 eventra-local`, then from the project root use the pinned CLI: `supabase start --network-id eventra-local`. See [database setup](../../docs/database.md). The network's default binding is intent, not proof: some CLI/runtime versions may override it. Reject the stack if inspection finds any wildcard publication.

Operator diagnostics (inspect locally; do not paste tokens from `supabase status` into logs):

```bash
# Confirm every published port is IPv4 loopback, including optional services.
docker ps --format 'table {{.Names}}\t{{.Ports}}'
ss -ltnp
docker network inspect eventra-local
docker stats --no-stream
# Confirm Redis resource limits and data policy.
docker compose --env-file infra/local/.env -f infra/local/compose.yaml exec redis redis-cli CONFIG GET maxmemory maxmemory-policy
curl --fail http://127.0.0.1:3000/api/v1/health/live
```

Inspect Windows listeners too (`Get-NetTCPConnection -State Listen`) and verify the workstation's LAN address cannot reach published ports. Do not terminate an unknown listener to free a port. Docker Engine 28+ is the baseline because older releases have documented loopback publication caveats. Avoid running Windows and WSL Ollama simultaneously on 11434. Supabase Auth, Storage and Realtime are retained; analytics, edge functions, pooler and external integrations are disabled. Studio 54323 and mail capture 54324 are operator-only tools.

Current scaffold evidence: these are configuration files, not proof of a running container stack. Docker, Supabase and Caddy must be installed and qualified before database mode can be accepted.

References: [Docker port publishing](https://docs.docker.com/engine/network/port-publishing/), [Caddy reverse proxy](https://caddyserver.com/docs/caddyfile/directives/reverse_proxy), [Supabase local configuration](https://supabase.com/docs/guides/local-development/cli/config).
