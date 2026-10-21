import asyncio
import json
from uuid import uuid4

import httpx
import pytest

from app.catalogue import CatalogueUnavailable, FIXTURES
from app.inference import InferenceGate, QueueExpired, QueueFull
from app.main import create_app
from app.settings import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


def model_transport(answer=None, installed=True, status=200):
    async def handler(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}] if installed else []})
        assert request.url.path == "/api/chat"
        payload = json.loads(request.content)
        assert payload["model"] == "qwen3.5:4b"
        assert payload["options"]["num_ctx"] == 2048
        assert payload["options"]["num_predict"] == 512
        assert payload["stream"] is False
        assert "tools" not in payload
        assert payload["format"]["type"] == "object"
        content = answer or {"message": "The Midnight Collective suits an indie soul evening in Mumbai. This is fictional preview data.", "artist_ids": [str(FIXTURES[0].id)]}
        return httpx.Response(status, json={"done": True, "done_reason": "stop", "message": {"content": json.dumps(content)}})
    return httpx.MockTransport(handler)


def client_for(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000")


@pytest.mark.anyio
async def test_catalogue_filtering_prices_and_details():
    async with client_for(create_app(Settings(), model_transport())) as client:
        all_artists = (await client.get("/api/v1/artists")).json()
        assert all_artists["total"] == 8
        assert all_artists["mode"] == "fixtures"
        assert all("fictional" in artist["description"] for artist in all_artists["items"])
        assert all(3500000 <= artist["price_paise"] <= 18000000 for artist in all_artists["items"])
        filtered = (await client.get("/api/v1/artists", params={"category": "DJ", "city": "mumbai", "max_price_paise": 8500000})).json()
        assert [artist["slug"] for artist in filtered["items"]] == ["dj-neel"]
        assert (await client.get("/api/v1/artists", params={"search": "INDIE"})).json()["total"] == 2
        assert (await client.get("/api/v1/artists", params={"max_price_paise": 0})).json()["items"] == []
        assert (await client.get("/api/v1/artists", params={"max_price_paise": -1})).status_code == 422
        assert (await client.get("/api/v1/artists", params={"category": "unknown"})).status_code == 422
        assert (await client.get("/api/v1/artists", params={"search": "x" * 121})).status_code == 422
        assert (await client.get(f"/api/v1/artists/{FIXTURES[0].id}")).json()["name"] == FIXTURES[0].name
        assert (await client.get(f"/api/v1/artists/{uuid4()}")).status_code == 404
        assert (await client.get("/api/v1/artists/not-a-uuid")).status_code == 422


@pytest.mark.anyio
async def test_preview_health_never_falsely_certifies_readiness():
    async with client_for(create_app(Settings(), model_transport())) as client:
        response = await client.get("/api/v1/health/ready")
        assert response.status_code == 503
        result = response.json()
        assert result["status"] == "preview"
        assert result["phase1_complete"] is False
        assert result["services"]["database"]["status"] == "unavailable"
        assert result["services"]["ollama"]["status"] == "ready"
        assert (await client.get("/api/v1/health/live")).status_code == 200


@pytest.mark.anyio
async def test_liveness_does_not_probe_downstream_services():
    def forbidden_probe(request):
        pytest.fail("Liveness must not call Ollama")
    app = create_app(Settings(), httpx.MockTransport(forbidden_probe))
    async with client_for(app) as client:
        response = await client.get("/api/v1/health/live")
        assert response.status_code == 200
        assert response.json()["services"]["ollama"]["status"] == "not_checked"


@pytest.mark.anyio
async def test_uninstalled_model_and_unreachable_provider_are_not_fake_success():
    app = create_app(Settings(), model_transport(installed=False))
    async with client_for(app) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie soul wedding in Mumbai"})
        assert response.status_code == 503
        assert "not installed" in response.json()["detail"]
        assert app.state.inference_gate.admitted == 0

    def unreachable(request):
        raise httpx.ConnectError("provider down", request=request)
    async with client_for(create_app(Settings(), httpx.MockTransport(unreachable))) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie soul wedding in Mumbai"})
        assert response.status_code == 503
        assert "unavailable" in response.json()["detail"]


@pytest.mark.anyio
async def test_structured_answer_is_validated_before_sse_result():
    app = create_app(Settings(), model_transport())
    async with client_for(app) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie soul wedding in Mumbai", "artist_ids": [str(FIXTURES[0].id)]})
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        assert response.text.index("event: status") < response.text.index("event: result") < response.text.index("event: done")
        assert str(FIXTURES[0].id) in response.text
        assert "event: error" not in response.text
        assert app.state.inference_gate.admitted == 0


@pytest.mark.anyio
async def test_database_catalogue_stays_browsable_but_default_ai_evidence_is_capped():
    records = [FIXTURES[index % 8].model_copy(update={"id": uuid4()}) for index in range(200)]
    sent_catalogues = []

    async def provider(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
        payload = json.loads(request.content)
        evidence = json.loads(payload["messages"][1]["content"])["fictional_catalogue"]
        sent_catalogues.append(evidence)
        content = {"message": "Consider the selected fictional artist.", "artist_ids": [evidence[0]["id"]]}
        return httpx.Response(200, json={"done": True, "message": {"content": json.dumps(content)}})

    app = create_app(Settings(database_url="postgresql://eventra_app:dummy@127.0.0.1:54322/postgres"), httpx.MockTransport(provider))
    async def database_records():
        return records
    app.state.catalogue.all = database_records
    async with client_for(app) as client:
        response = await client.get("/api/v1/artists")
        assert response.json()["mode"] == "database"
        assert response.json()["total"] == 200
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie wedding in Mumbai"})
        assert "event: result" in response.text
        assert [item["id"] for item in sent_catalogues[-1]] == [str(artist.id) for artist in records[:8]]
        requested_ids = [str(artist.id) for artist in records[-8:]]
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie wedding in Mumbai", "artist_ids": requested_ids})
        assert "event: result" in response.text
        assert [item["id"] for item in sent_catalogues[-1]] == requested_ids


@pytest.mark.anyio
async def test_ai_cannot_return_an_id_outside_its_bounded_database_evidence():
    records = [FIXTURES[index % 8].model_copy(update={"id": uuid4()}) for index in range(200)]
    app = create_app(Settings(), model_transport(answer={"message": "A record outside the eight-item model evidence", "artist_ids": [str(records[9].id)]}))
    async def database_records():
        return records
    app.state.catalogue.all = database_records
    async with client_for(app) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie wedding in Mumbai"})
        assert "event: error" in response.text
        assert "event: result" not in response.text


@pytest.mark.anyio
@pytest.mark.parametrize("bad_answer", [
    {"message": "Invented recommendation", "artist_ids": [str(uuid4())]},
    {"message": "Wrong selected artist", "artist_ids": [str(FIXTURES[1].id)]},
    {"message": "Duplicate recommendations", "artist_ids": [str(FIXTURES[0].id), str(FIXTURES[0].id)]},
    {"message": "Not schema compliant", "artist_ids": [], "booking_confirmed": True},
    {"message": 123, "artist_ids": []},
])
async def test_hallucinated_ids_and_invalid_schema_are_discarded(bad_answer):
    app = create_app(Settings(), model_transport(answer=bad_answer))
    async with client_for(app) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie soul wedding in Mumbai", "artist_ids": [str(FIXTURES[0].id)]})
        assert "event: error" in response.text
        assert "event: result" not in response.text
        assert bad_answer["message"] not in response.text if isinstance(bad_answer["message"], str) else True
        assert app.state.inference_gate.admitted == 0


@pytest.mark.anyio
async def test_generation_failure_is_recoverable_stream_error():
    async with client_for(create_app(Settings(), model_transport(status=503))) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie soul wedding in Mumbai"})
        assert response.status_code == 200  # Headers already sent for SSE.
        assert "event: error" in response.text
        assert "event: result" not in response.text


@pytest.mark.anyio
async def test_request_schema_and_browser_boundary():
    async with client_for(create_app(Settings(), model_transport())) as client:
        for payload in [
            {"brief": "x" * 1201}, {"brief": 123}, {"brief": "    "},
            {"brief": "न" * 550},
            {"brief": "An indie wedding", "model_url": "https://hosted.invalid"},
            {"brief": "An indie wedding", "artist_ids": ["malformed"]},
            {"brief": "An indie wedding", "artist_ids": [str(uuid4())]},
            {"brief": "An indie wedding", "artist_ids": [str(FIXTURES[0].id)] * 2},
        ]:
            assert (await client.post("/api/v1/assistant/runs", json=payload)).status_code == 422
        assert (await client.post("/api/v1/assistant/runs", json={"brief": "An indie wedding"}, headers={"Origin": "https://remote.invalid"})).status_code == 403
        assert (await client.post("/api/v1/assistant/runs", content='{"brief":"An indie wedding"}', headers={"Content-Type": "text/plain"})).status_code == 415
        assert (await client.get("/api/v1/artists", headers={"Host": "rebound.invalid"})).status_code == 400
        assert (await client.post("/api/v1/assistant/runs", content='{"brief":"' + "x" * 9000 + '"}', headers={"Content-Type": "application/json"})).status_code == 413


@pytest.mark.parametrize("url", ["https://api.openai.com", "http://192.168.1.2:11434", "http://127.0.0.1:11434/proxy", "http://user:pass@127.0.0.1:11434", "http://127.0.0.1:11434?url=other", "http://myhost:11434"])
def test_remote_or_ambiguous_model_urls_fail_at_boot(url):
    with pytest.raises(ValueError):
        Settings(inference_base_url=url)


def test_database_must_remain_loopback_and_fixed_port():
    for url in ["postgresql://user:secret@db.example:54322/postgres", "postgresql://user:secret@127.0.0.1:5432/postgres", "postgresql://u:p@127.0.0.1:54322/postgres?host=remote"]:
        with pytest.raises(ValueError):
            Settings(database_url=url)


@pytest.mark.anyio
async def test_configured_database_failure_never_silently_falls_back():
    app = create_app(Settings(database_url="postgresql://eventra_app:dummy@127.0.0.1:54322/postgres"), model_transport())
    def unavailable():
        raise RuntimeError("password=must-never-leak")
    app.state.catalogue._read_database = unavailable
    async with client_for(app) as client:
        response = await client.get("/api/v1/artists")
        assert response.status_code == 503
        assert "must-never-leak" not in response.text
        health = (await client.get("/api/v1/health/ready")).json()
        assert health["data_mode"] == "database"
        assert health["services"]["database"]["status"] == "unavailable"


@pytest.mark.anyio
async def test_endpoint_rejects_fourth_admitted_request():
    app = create_app(Settings(), model_transport())
    tickets = [await app.state.inference_gate.reserve() for _ in range(3)]
    async with client_for(app) as client:
        response = await client.post("/api/v1/assistant/runs", json={"brief": "An indie wedding in Mumbai"})
        assert response.status_code == 429
        assert response.headers["retry-after"] == "5"
    for ticket in tickets:
        await ticket.release()
    assert app.state.inference_gate.admitted == 0


@pytest.mark.anyio
async def test_gate_one_active_two_waiting_and_timeout_release():
    gate = InferenceGate(wait_seconds=0.03)
    first, second, third = [await gate.reserve() for _ in range(3)]
    with pytest.raises(QueueFull):
        await gate.reserve()
    async with first.activation():
        assert gate.active == 1
        async def wait_for_lane(ticket):
            with pytest.raises(QueueExpired):
                async with ticket.activation():
                    pytest.fail("Only one inference request may run")
        await asyncio.gather(wait_for_lane(second), wait_for_lane(third))
        assert gate.admitted == 1
    assert gate.active == 0
    assert gate.admitted == 0


@pytest.mark.anyio
async def test_cancelled_active_and_queued_tickets_release_capacity():
    gate = InferenceGate()
    started = asyncio.Event()
    async def active_job():
        ticket = await gate.reserve()
        async with ticket.activation():
            started.set()
            await asyncio.sleep(60)
    task = asyncio.create_task(active_job())
    await started.wait()
    queued_ticket = await gate.reserve()
    async def queued_job():
        async with queued_ticket.activation():
            pytest.fail("Cancelled queue entry must not run")
    queued_task = asyncio.create_task(queued_job())
    await asyncio.sleep(0)
    queued_task.cancel()
    await asyncio.gather(queued_task, return_exceptions=True)
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    assert gate.active == 0
    assert gate.admitted == 0


@pytest.mark.anyio
async def test_browser_disconnect_cancels_model_request_and_releases_lane():
    provider_started = asyncio.Event()
    provider_cancelled = asyncio.Event()

    async def provider(request):
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "qwen3.5:4b"}]})
        provider_started.set()
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            provider_cancelled.set()
            raise
        pytest.fail("Disconnected request must not finish generation")

    app = create_app(Settings(), httpx.MockTransport(provider))
    body = json.dumps({"brief": "An indie wedding in Mumbai"}).encode()
    delivered_body = False
    frames = []

    async def receive():
        nonlocal delivered_body
        if not delivered_body:
            delivered_body = True
            return {"type": "http.request", "body": body, "more_body": False}
        await provider_started.wait()
        return {"type": "http.disconnect"}

    async def send(message):
        frames.append(message)

    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "scheme": "http", "method": "POST",
        "path": "/api/v1/assistant/runs", "raw_path": b"/api/v1/assistant/runs",
        "query_string": b"", "root_path": "",
        "headers": [(b"host", b"127.0.0.1:8000"), (b"content-type", b"application/json")],
        "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 40000),
    }
    await asyncio.wait_for(app(scope, receive, send), timeout=2)
    assert provider_cancelled.is_set()
    assert app.state.inference_gate.admitted == 0
    assert app.state.inference_gate.active == 0
    assert b"event: result" not in b"".join(frame.get("body", b"") for frame in frames)


@pytest.mark.anyio
@pytest.mark.parametrize("disconnect", [False, True])
async def test_chunked_body_limit_and_incomplete_upload_disconnect(disconnect):
    def forbidden_probe(request):
        pytest.fail("An oversized or incomplete request must never reach Ollama")
    app = create_app(Settings(), httpx.MockTransport(forbidden_probe))
    messages = [
        {"type": "http.request", "body": b'{"brief":"' + b"x" * 4000, "more_body": True},
        {"type": "http.disconnect"} if disconnect else {"type": "http.request", "body": b"x" * 5000 + b'"}', "more_body": False},
    ]
    frames = []
    async def receive():
        if messages:
            return messages.pop(0)
        return {"type": "http.disconnect"}
    async def send(message):
        frames.append(message)
    scope = {
        "type": "http", "asgi": {"version": "3.0", "spec_version": "2.4"},
        "http_version": "1.1", "scheme": "http", "method": "POST",
        "path": "/api/v1/assistant/runs", "raw_path": b"/api/v1/assistant/runs",
        "query_string": b"", "root_path": "",
        "headers": [(b"host", b"127.0.0.1:8000"), (b"content-type", b"application/json")],
        "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 40000),
    }
    await app(scope, receive, send)
    assert next(frame["status"] for frame in frames if frame["type"] == "http.response.start") == (499 if disconnect else 413)
    assert app.state.inference_gate.admitted == 0
