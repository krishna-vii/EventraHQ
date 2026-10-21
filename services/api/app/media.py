"""Bounded image upload to private Supabase Storage using the actual user's JWT."""
import asyncio
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, Request, Response
import httpx


def image_extension(data: bytes, mime: str):
    if mime == "image/jpeg" and data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if mime == "image/png" and data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if mime == "image/webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    raise HTTPException(415, "Upload a JPEG, PNG or WebP image matching its content type.")


def install_media(app, settings):
    r = APIRouter(prefix="/api/v1")

    @r.put("/artist/portfolio")
    async def upload(request: Request):
        user = await app.state.auth.identity(request)
        profile = await app.state.database.call("artist_me", actor=user["id"])
        if not profile.get("artist"):
            raise HTTPException(409, "Create your artist profile before uploading a portfolio.")
        if len(profile["gallery"]) >= 10:
            raise HTTPException(409, "Your portfolio already has ten images.")
        body = bytearray()
        try:
            async with asyncio.timeout(20):
                async for chunk in request.stream():
                    if len(body)+len(chunk) > 5242880:
                        raise HTTPException(413, "Portfolio images must be at most 5 MB.")
                    body.extend(chunk)
        except TimeoutError:
            raise HTTPException(408, "Image upload timed out.")
        mime = request.headers.get("content-type", "").split(";")[0]
        extension = image_extension(body, mime)
        path = f"{user['id']}/{profile['artist']['id']}/{uuid4()}.{extension}"
        headers = {"apikey": settings.supabase_key, "Authorization": f"Bearer {user['token']}", "Content-Type": mime, "x-upsert": "false"}
        try:
            async with httpx.AsyncClient(base_url=settings.supabase_url, timeout=20, trust_env=False, follow_redirects=False) as client:
                response = await client.post(f"/storage/v1/object/artist-portfolios/{path}", headers=headers, content=body)
                response.raise_for_status()
                try:
                    return await app.state.database.call("media_add", {"path": path, "content_type": mime}, user["id"])
                except Exception:
                    await client.request("DELETE", "/storage/v1/object/artist-portfolios", headers={k:v for k,v in headers.items() if k!="Content-Type"}, json={"prefixes": [path]})
                    raise
        except httpx.HTTPError:
            raise HTTPException(503, "Portfolio storage is unavailable. Check the bucket and policies.") from None

    @r.get("/media/{media_id}")
    async def media(media_id: UUID, request: Request):
        # Public published media resolves without a user; drafts require verified ownership.
        token = None
        actor = None
        if request.cookies.get("eventra_access"):
            user = await app.state.auth.identity(request)
            token, actor = user["token"], user["id"]
        item = await app.state.database.call("media_path", {"media_id": str(media_id)}, actor)
        headers = {"apikey": settings.supabase_key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        elif settings.supabase_key.startswith("eyJ"):
            headers["Authorization"] = f"Bearer {settings.supabase_key}"
        try:
            async with httpx.AsyncClient(base_url=settings.supabase_url, timeout=15, trust_env=False, follow_redirects=False) as client:
                response = await client.get(f"/storage/v1/object/authenticated/artist-portfolios/{item['path']}", headers=headers)
                response.raise_for_status()
            return Response(response.content, media_type=item["content_type"], headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"})
        except httpx.HTTPError:
            raise HTTPException(503, "This portfolio image is temporarily unavailable.") from None

    app.include_router(r)
