"""Supabase verifies credentials and tokens. Browser sessions never contain role authority."""
from typing import Annotated, Literal
from uuid import UUID
import re
import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator


class Login(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Annotated[str, Field(min_length=3, max_length=254)]
    password: Annotated[str, Field(min_length=12, max_length=128)]

    @field_validator("email")
    @classmethod
    def email_format(cls, value):
        if "@" not in value or any(c.isspace() for c in value):
            raise ValueError("Enter a valid email address.")
        return value.strip().lower()


class Registration(Login):
    display_name: Annotated[str, Field(min_length=1, max_length=120)]


class Verification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token_hash: str = Field(min_length=16, max_length=256)
    type: Literal["signup", "email", "recovery"]


class Recovery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: str = Field(min_length=3, max_length=254)


class PasswordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    password: str = Field(min_length=12, max_length=128)


class SupabaseAuth:
    def __init__(self, settings, transport=None):
        self.settings = settings
        self.transport = transport

    @property
    def configured(self):
        return bool(self.settings.supabase_url and self.settings.supabase_key and self.settings.database_url)

    async def call(self, path, *, body=None, token=None, method=None):
        if not self.configured:
            raise HTTPException(503, "Supabase account service is not configured. Follow docs/DEPLOYMENT.md before registering or logging in.")
        headers = {"apikey": self.settings.supabase_key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(base_url=self.settings.supabase_url, timeout=10, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                response = await client.request(method or ("POST" if body is not None else "GET"), f"/auth/v1/{path}", json=body, headers=headers)
            if response.status_code >= 300:
                raise HTTPException(401 if response.status_code in (400, 401, 403, 422) else 503, "Account verification failed. Check your credentials and email verification, or retry shortly.")
            data = response.json() if response.content else {}
            if not isinstance(data, dict):
                raise ValueError("Invalid account response")
            return data
        except (httpx.HTTPError, ValueError):
            raise HTTPException(503, "The account service is temporarily unavailable.") from None

    async def identity(self, request: Request):
        token = request.cookies.get("eventra_access")
        header = request.headers.get("authorization", "")
        if header.startswith("Bearer "):
            token = header[7:]
        if not token:
            raise HTTPException(401, "Log in to continue.")
        user = await self.call("user", token=token)
        try:
            user_id = str(UUID(user["id"]))
        except (KeyError, ValueError, TypeError):
            raise HTTPException(401, "The account service returned an invalid identity.")
        await request.app.state.database.call("authorize", actor=user_id)
        return {"id": user_id, "email": user.get("email", ""), "token": token}


def install_auth(app, settings):
    router = APIRouter(prefix="/api/v1")
    auth = SupabaseAuth(settings)
    app.state.auth = auth

    def session_cookies(response, data, *, allow_confirmation=False):
        # Validate the complete session before setting either cookie. A signup can
        # instead return a user awaiting email confirmation, without any tokens.
        if allow_confirmation and "access_token" not in data and "refresh_token" not in data:
            try:
                UUID(data["id"])
            except (KeyError, ValueError, TypeError, AttributeError):
                raise HTTPException(503, "The account service returned an incomplete registration. Please retry.") from None
            return False
        tokens = [data.get("access_token"), data.get("refresh_token")]
        duration = data.get("expires_in")
        if (
            any(not isinstance(token, str) or not 1 <= len(token) <= 3800 or re.fullmatch(r"[A-Za-z0-9._~+/=-]+", token) is None for token in tokens)
            or type(duration) is not int or duration <= 0
        ):
            raise HTTPException(503, "The account service returned an incomplete session. Please log in again.")
        for name, token, lifetime in [("eventra_access", tokens[0], min(duration, 3600)), ("eventra_refresh", tokens[1], 604800)]:
            response.set_cookie(name, token, httponly=True, secure=settings.app_env != "local", samesite="strict", path="/api/v1", max_age=lifetime)
        return True

    @router.get("/session")
    async def session(request: Request):
        if not request.cookies.get("eventra_access") and request.cookies.get("eventra_refresh"):
            raise HTTPException(401, "Refresh your session.")
        if not request.cookies.get("eventra_access") and not request.headers.get("authorization"):
            return {"user": None, "configured": auth.configured}
        try:
            user = await auth.identity(request)
            profile = await app.state.database.call("profile", actor=user["id"])
            return {"user": {"id": user["id"], "email": user["email"]}, "roles": profile["roles"], "configured": auth.configured}
        except HTTPException as error:
            if error.status_code == 401 and not request.cookies.get("eventra_refresh"):
                return {"user": None, "configured": auth.configured}
            raise

    @router.post("/auth/register")
    async def register(body: Registration, response: Response):
        data = await auth.call("signup", body={"email": body.email, "password": body.password, "data": {"display_name": body.display_name}})
        authenticated = session_cookies(response, data, allow_confirmation=True)
        return {"authenticated": authenticated, "message": "If eligible, your account has been created. Check your email to verify, then log in."}

    @router.post("/auth/login")
    async def login(body: Login, response: Response):
        data = await auth.call("token?grant_type=password", body=body.model_dump())
        session_cookies(response, data)
        return {"authenticated": True, "message": "Logged in."}

    @router.post("/auth/refresh")
    async def refresh(request: Request, response: Response):
        token = request.cookies.get("eventra_refresh")
        if not token:
            raise HTTPException(401, "Log in again to continue.")
        data = await auth.call("token?grant_type=refresh_token", body={"refresh_token": token})
        session_cookies(response, data)
        return {"authenticated": True}

    @router.post("/auth/logout")
    async def logout(request: Request, response: Response):
        token = request.cookies.get("eventra_access")
        # An expired access cookie with a remaining refresh cookie does not prove
        # provider revocation. Local cookie removal still succeeds in this case.
        revoked = not bool(request.cookies.get("eventra_refresh"))
        if token:
            try:
                await auth.call("logout", token=token, body={})
                revoked = True
            except HTTPException:
                revoked = False
        response.delete_cookie("eventra_access", path="/api/v1")
        response.delete_cookie("eventra_refresh", path="/api/v1")
        return {"message": "Logged out on this device.", "provider_session_revoked": revoked}

    @router.post("/auth/recover")
    async def recover(body: Recovery):
        await auth.call("recover", body={"email": body.email})
        return {"message": "If an account matches, a recovery email will be sent."}

    @router.post("/auth/verify")
    async def verify(body: Verification, response: Response):
        data = await auth.call("verify", body=body.model_dump())
        session_cookies(response, data)
        return {"authenticated": True}

    @router.post("/auth/password")
    async def password(body: PasswordUpdate, request: Request):
        user = await auth.identity(request)
        await auth.call("user", body=body.model_dump(), token=user["token"], method="PUT")
        return {"message": "Password updated."}

    app.include_router(router)
