import asyncio
import json
import logging
import time
from typing import Annotated
from uuid import UUID
from datetime import date
from typing import Literal
from .discovery import eligible

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.background import BackgroundTask
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import ClientDisconnect

from .catalogue import Catalogue, CatalogueUnavailable
from .inference import InferenceGate, InferenceUnavailable, InvalidModelAnswer, Ollama, HostedAI, QueueExpired, QueueFull
from .models import Artist, ArtistList, AssistantRequest, Category, MAX_EVIDENCE_ARTISTS
from .settings import Settings
from .auth import install_auth
from .persistence import Database
from .workflows import install_workflows
from .payments import install_payments
from .media import install_media
from .security import RateLimit


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def create_app(settings: Settings | None = None, ollama_transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    catalogue = Catalogue(settings)
    ollama = (HostedAI if settings.inference_provider == "hosted" else Ollama)(settings, ollama_transport)
    gate = InferenceGate(settings.queue_wait_seconds)
    limiter = RateLimit()
    app = FastAPI(
        title="EventraHQ marketplace API", version="0.2.0",
        docs_url=None, redoc_url=None, openapi_url="/api/v1/openapi.json",
        description="Artist marketplace. Business features require configured Supabase and applied migrations. Payments require verified provider webhooks.",
    )
    app.state.settings = settings
    app.state.catalogue = catalogue
    app.state.ollama = ollama
    app.state.inference_gate = gate
    app.state.database = Database(settings)
    install_auth(app, settings)
    install_workflows(app)
    install_payments(app, settings)
    install_media(app, settings)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "[::1]"] + ([settings.api_hostname] if settings.api_hostname else []))

    @app.middleware("http")
    async def local_browser_boundary(request: Request, call_next):
        started = time.monotonic()
        request_id = __import__('uuid').uuid4().hex
        origin = request.headers.get("origin")
        if origin and origin != settings.app_origin:
            return JSONResponse(status_code=403, content={"detail": "Use the canonical local EventraHQ origin."})
        if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.headers.get("cookie") and origin != settings.app_origin:
            return JSONResponse(status_code=403, content={"detail": "Session writes require the configured application origin."})
        if request.method == "POST" and request.url.path.startswith("/api/v1/auth/"):
            # Never trust client-supplied forwarding headers for identity or rate limits.
            if not limiter.allow("auth:" + (request.client.host if request.client else "unknown"), 20):
                return JSONResponse(status_code=429, content={"detail": "Too many account requests. Retry in one minute."}, headers={"Retry-After": "60"})
        if request.method == "POST" and request.headers.get("content-type", "").split(";")[0].lower() != "application/json":
            return JSONResponse(status_code=415, content={"detail": "Use application/json."})
        if request.method == "POST":
            body = bytearray()
            maximum = 8192 if request.url.path == "/api/v1/assistant/runs" else 65536
            try:
                async with asyncio.timeout(5):
                    async for chunk in request.stream():
                        if len(body) + len(chunk) > maximum:
                            return JSONResponse(status_code=413, content={"detail": "The request exceeds the 8 KiB local preview limit."})
                        body.extend(chunk)
            except ClientDisconnect:
                return JSONResponse(status_code=499, content={"detail": "The client disconnected before completing its request."})
            except TimeoutError:
                return JSONResponse(status_code=408, content={"detail": "Send the complete local request within five seconds."})
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Request-ID"] = request_id
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        logging.getLogger("eventrahq").info("request id=%s method=%s path=%s status=%s duration_ms=%d", request_id, request.method, request.url.path, response.status_code, (time.monotonic()-started)*1000)
        return response

    @app.exception_handler(CatalogueUnavailable)
    async def catalogue_error(request: Request, error: CatalogueUnavailable):
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.get("/api/v1/artists", response_model=ArtistList)
    async def artists(
        search: Annotated[str, Query(max_length=120)] = "",
        category: Category | None = None,
        city: Annotated[str, Query(max_length=80)] = "",
        max_price_paise: Annotated[int | None, Query(ge=0, le=1000000000)] = None,
        genre: Annotated[str, Query(max_length=80)] = "",
        event_type: Annotated[str, Query(max_length=80)] = "",
        event_date: date | None = None,
        sort: Literal["recommended", "price_low", "price_high", "name"] = "recommended",
        page: Annotated[int, Query(ge=1, le=10000)] = 1,
        page_size: Annotated[int, Query(ge=1, le=200)] = 24,
    ):
        if catalogue.mode == "database" and "all" not in catalogue.__dict__:
            items, total = await catalogue.search(search=search.strip(), category=category, city=city.strip(), genre=genre.strip(), event_type=event_type, max_price_paise=max_price_paise, event_date=event_date, sort=sort, page=page, page_size=page_size)
            return ArtistList(items=items, total=total, mode=catalogue.mode, page=page, page_size=page_size)
        items = await eligible(catalogue, search=search, category=category, city=city, genre=genre, event_type=event_type, max_price_paise=max_price_paise, event_date=event_date)
        if sort in ("price_low", "price_high"):
            items.sort(key=lambda a: (a.price_paise, a.name, str(a.id)), reverse=sort == "price_high")
        elif sort == "name":
            items.sort(key=lambda a: (a.name.casefold(), str(a.id)))
        total = len(items)
        return ArtistList(items=items[(page-1)*page_size:page*page_size], total=total, mode=catalogue.mode, page=page, page_size=page_size)

    @app.get("/api/v1/artists/by-slug/{slug}", response_model=Artist)
    async def artist_slug(slug: str):
        item = next((a for a in await catalogue.all() if a.slug == slug), None)
        if not item:
            raise HTTPException(404, "Artist not found.")
        return item

    @app.get("/api/v1/artists/{artist_id}", response_model=Artist)
    async def artist_detail(artist_id: UUID):
        artist = await catalogue.find(artist_id)
        if artist is None:
            raise HTTPException(status_code=404, detail="Artist not found in the public preview catalogue.")
        return artist

    async def health_payload(live: bool) -> dict:
        database, inference = await asyncio.gather(catalogue.health(), ollama.health())
        return {
            "status": "live" if live else "preview",
            "data_mode": catalogue.mode,
            "phase1_complete": False,
            "services": {"database": database, "ollama": inference},
            "message": "Read-only discovery preview. Phase 1 authentication, transactional flows and workstation qualification are incomplete.",
        }

    @app.get("/api/v1/health/live")
    async def live():
        # Liveness must not fail or stall because a downstream service is absent.
        return {
            "status": "live", "data_mode": catalogue.mode, "phase1_complete": False,
            "services": {
                "database": {"status": "not_checked", "message": "Dependency checks belong to /health/ready."},
                "ollama": {"status": "not_checked", "message": "Dependency checks belong to /health/ready."},
            },
        }

    @app.get("/api/v1/health/ready")
    async def ready():
        payload = await health_payload(False)
        operational = payload["services"]["database"]["status"] == "ready" and app.state.auth.configured
        payload["status"] = "ready" if operational else "preview"
        payload["message"] = "Operational dependency readiness only. Full transaction, provider and release acceptance is tracked in docs/BUILD_STATUS.md."
        return JSONResponse(status_code=200 if operational else 503, content=payload)

    @app.post("/api/v1/assistant/runs")
    async def assistant(body: AssistantRequest, request: Request):
        items = await eligible(catalogue, city=body.city, event_type=body.event_type, max_price_paise=body.max_price_paise, event_date=body.event_date)
        by_id = {artist.id: artist for artist in items}
        if body.artist_ids and not set(body.artist_ids).issubset(by_id):
            raise HTTPException(status_code=422, detail="A selected artist is outside the public preview catalogue.")
        # The catalogue may contain 200 DB rows; the compact model never receives more than eight.
        selection = [by_id[artist_id] for artist_id in body.artist_ids] if body.artist_ids else items[:MAX_EVIDENCE_ARTISTS]
        if not selection:
            return StreamingResponse(iter([sse("result", {"message": "No published artists match these filters. Try another city, budget or date. No availability or booking has been assumed.", "artist_ids": []}), sse("done", {"status": "complete"})]), media_type="text/event-stream")
        inference_health = await ollama.health()
        if inference_health["status"] != "ready":
            raise HTTPException(status_code=503, detail=inference_health["message"])
        try:
            ticket = await gate.reserve()
        except QueueFull:
            raise HTTPException(status_code=429, detail="The local model has one active request and two waiting. Please retry shortly.", headers={"Retry-After": "5"})

        async def events():
            try:
                yield sse("status", {"phase": "queued", "message": "Waiting for the local model."})
                async with ticket.activation():
                    if await request.is_disconnected():
                        return
                    yield sse("status", {"phase": "generating", "message": "Reviewing eligible catalogue records."})
                    generation = asyncio.create_task(ollama.recommend(body.brief, selection))
                    async def wait_for_disconnect():
                        while True:
                            message = await request.receive()
                            if message["type"] == "http.disconnect":
                                return
                    disconnect = asyncio.create_task(wait_for_disconnect())
                    try:
                        finished, _ = await asyncio.wait([generation, disconnect], return_when=asyncio.FIRST_COMPLETED)
                        if disconnect in finished:
                            return
                        answer = await generation
                    finally:
                        generation.cancel()
                        disconnect.cancel()
                        await asyncio.gather(generation, disconnect, return_exceptions=True)
                    if await request.is_disconnected():
                        return
                    yield sse("result", answer.model_dump(mode="json"))
                    yield sse("done", {"status": "complete"})
            except QueueExpired:
                yield sse("error", {"message": "The local model queue timed out. Please retry shortly."})
            except (InferenceUnavailable, InvalidModelAnswer) as error:
                yield sse("error", {"message": str(error)})
            finally:
                await asyncio.shield(ticket.release())

        return StreamingResponse(
            events(), media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
            background=BackgroundTask(ticket.release),
        )

    return app


app = create_app()
