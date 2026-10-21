"""Provider contract tests; these do not create real Supabase accounts."""
from uuid import uuid4

import httpx
import pytest

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


VALID_SESSION = {"access_token": "test-access", "refresh_token": "test-refresh", "expires_in": 3600}
LOGIN = {"email": "member@example.com", "password": "long-enough-password"}
BODIES = {
    "login": LOGIN,
    "register": {**LOGIN, "display_name": "Member"},
    "refresh": {},
    "verify": {"token_hash": "test-verification-hash", "type": "signup"},
}


def application(provider_data, *, status=200, hosted=False):
    settings = Settings(
        database_url="postgresql://eventra_app:dummy@127.0.0.1:54322/postgres",
        supabase_url="http://127.0.0.1:54321", supabase_key="test-publishable",
        **({"app_env": "staging", "app_origin": "https://eventra.example", "api_hostname": "api.eventra.example"} if hosted else {}),
    )
    app = create_app(settings)
    app.state.auth.transport = httpx.MockTransport(lambda _: httpx.Response(status, json=provider_data))
    return app


async def post(app, route):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=app.state.settings.app_origin) as client:
        headers = {"Origin": app.state.settings.app_origin}
        if route == "refresh":
            headers["Cookie"] = "eventra_refresh=previous-refresh"
        return await client.post("/api/v1/auth/" + route, json=BODIES[route], headers=headers)


@pytest.mark.anyio
@pytest.mark.parametrize("route", BODIES)
@pytest.mark.parametrize("data", [
    {}, [], None,
    {"access_token": "partial-access", "expires_in": 3600},
    {"refresh_token": "partial-refresh", "expires_in": 3600},
])
async def test_incomplete_provider_responses_never_authenticate_or_set_cookies(route, data):
    response = await post(application(data), route)
    assert response.status_code == 503
    assert "set-cookie" not in response.headers
    assert "partial-access" not in response.text
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
@pytest.mark.parametrize("change", [
    {"expires_in": "3600"}, {"expires_in": True}, {"expires_in": 0},
    {"expires_in": -1}, {"expires_in": None}, {"expires_in": 1.5},
    {"access_token": ""}, {"refresh_token": 123},
    {"access_token": "token\r\nInjected: value"}, {"refresh_token": "x" * 3801},
])
async def test_invalid_cookie_values_and_expiries_fail_atomically(change):
    response = await post(application({**VALID_SESSION, **change}), "login")
    assert response.status_code == 503
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
async def test_pending_email_confirmation_does_not_claim_a_session():
    response = await post(application({"id": str(uuid4()), "identities": []}), "register")
    assert response.status_code == 200
    assert response.json()["authenticated"] is False
    assert "set-cookie" not in response.headers


@pytest.mark.anyio
@pytest.mark.parametrize("route", ["login", "refresh", "verify"])
async def test_valid_session_rotates_both_cookies_and_caps_access_lifetime(route):
    response = await post(application({**VALID_SESSION, "expires_in": 7200}), route)
    assert response.status_code == 200 and response.json()["authenticated"] is True
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2
    assert "eventra_access=test-access" in cookies[0] and "Max-Age=3600" in cookies[0]
    assert "eventra_refresh=test-refresh" in cookies[1] and "Max-Age=604800" in cookies[1]
    assert all("HttpOnly" in cookie and "Path=/api/v1" in cookie and "SameSite=strict" in cookie for cookie in cookies)


@pytest.mark.anyio
async def test_hosted_session_cookies_require_https():
    app = application(VALID_SESSION, hosted=True)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://api.eventra.example") as client:
        response = await client.post("/api/v1/auth/login", json=LOGIN, headers={"Origin": "https://eventra.example"})
    assert response.status_code == 200
    assert all("Secure" in value for value in response.headers.get_list("set-cookie"))


@pytest.mark.anyio
async def test_provider_redirect_cannot_be_accepted_as_a_session():
    response = await post(application(VALID_SESSION, status=302), "login")
    assert response.status_code == 503 and "set-cookie" not in response.headers


@pytest.mark.anyio
@pytest.mark.parametrize("cookie,provider_status,expected_revoked", [
    ("eventra_refresh=expired-access-session", 200, False),
    ("eventra_access=test-access; eventra_refresh=test-refresh", 204, True),
    ("eventra_access=test-access; eventra_refresh=test-refresh", 503, False),
])
async def test_logout_always_clears_local_cookies_and_reports_revocation_honestly(cookie, provider_status, expected_revoked):
    app = application({}, status=provider_status)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:3000") as client:
        response = await client.post("/api/v1/auth/logout", json={}, headers={"Origin": "http://127.0.0.1:3000", "Cookie": cookie})
    assert response.status_code == 200
    assert response.json()["provider_session_revoked"] is expected_revoked
    cookies = response.headers.get_list("set-cookie")
    assert len(cookies) == 2 and all("Max-Age=0" in cookie for cookie in cookies)
