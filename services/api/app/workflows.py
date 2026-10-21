"""HTTP validation and identity boundary; database functions own authorization and transactions."""
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileInput(Input):
    display_name: str = Field(min_length=1, max_length=120)
    phone: str | None = Field(default=None, min_length=5, max_length=30)


class ArtistInput(Input):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=120)
    category: Literal["Live band", "DJ", "Vocalist", "Instrumental"]
    city: str = Field(min_length=2, max_length=120)
    tagline: str = Field(min_length=5, max_length=180)
    description: str = Field(min_length=30, max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)
    price_paise: int = Field(ge=100, le=1000000000)
    event_types: list[Literal["Wedding", "Corporate event", "Private party", "Festival"]] = Field(min_length=1, max_length=4)


class Period(Input):
    starts_at: datetime
    ends_at: datetime

    @model_validator(mode="after")
    def valid_period(self):
        if not self.starts_at.tzinfo or not self.ends_at.tzinfo:
            raise ValueError("Dates must include a timezone.")
        if self.ends_at <= self.starts_at or (self.ends_at-self.starts_at).total_seconds() > 604800:
            raise ValueError("End must follow start, within seven days.")
        if self.starts_at <= datetime.now(timezone.utc):
            raise ValueError("Choose a future event time.")
        return self


class EventInput(Period):
    title: str = Field(min_length=2, max_length=160)
    city: str = Field(min_length=2, max_length=120)
    event_type: Literal["Wedding", "Corporate event", "Private party", "Festival"]
    budget_paise: int = Field(ge=100, le=1000000000)
    guest_count: int = Field(ge=1, le=100000)
    notes: str = Field(default="", max_length=4000)


class AvailabilityInput(Period):
    kind: Literal["open", "blocked"]


class SavedInput(Input):
    artist_id: UUID
    saved: bool


class InquiryInput(Input):
    event_id: UUID
    artist_id: UUID
    body: str = Field(min_length=1, max_length=4000)


class MessageInput(Input):
    body: str = Field(min_length=1, max_length=4000)
    client_nonce: UUID


class QuoteInput(Input):
    performance_paise: int = Field(ge=100, le=1000000000)
    travel_paise: int = Field(default=0, ge=0, le=100000000)
    equipment_paise: int = Field(default=0, ge=0, le=100000000)
    tax_paise: int = Field(default=0, ge=0, le=100000000)
    discount_paise: int = Field(default=0, ge=0, le=100000000)
    buffer_minutes: int = Field(default=60, ge=0, le=240)
    terms: str = Field(min_length=10, max_length=4000)
    valid_hours: int = Field(default=48, ge=1, le=168)
    client_nonce: UUID


class AcceptInput(Input):
    idempotency_key: UUID


class ModerationInput(Input):
    status: Literal["published", "draft", "suspended"]
    reason: str = Field(min_length=5, max_length=500)


class ReviewInput(Input):
    stars: int = Field(ge=1, le=5)
    body: str = Field(min_length=3, max_length=2000)


class UserModeration(Input):
    suspended: bool
    reason: str = Field(min_length=5, max_length=500)


def install_workflows(app):
    r = APIRouter(prefix="/api/v1")

    async def run(request, action, body=None, **values):
        actor = await app.state.auth.identity(request)
        payload = body.model_dump(mode="json") if body else {}
        payload.update({k: str(v) for k,v in values.items()})
        return await app.state.database.call(action, payload, actor["id"])

    @r.get("/me")
    async def me(request: Request): return await run(request, "profile")

    @r.post("/me")
    async def profile(body: ProfileInput, request: Request): return await run(request, "profile_save", body)

    @r.get("/saved")
    async def saved(request: Request): return await run(request, "saved_list")

    @r.post("/saved")
    async def save(body: SavedInput, request: Request): return await run(request, "saved_toggle", body)

    @r.get("/events")
    async def events(request: Request): return await run(request, "events_list")

    @r.post("/events")
    async def event(body: EventInput, request: Request): return await run(request, "event_create", body)

    @r.get("/artist/me")
    async def artist(request: Request): return await run(request, "artist_me")

    @r.post("/artist/me")
    async def artist_save(body: ArtistInput, request: Request): return await run(request, "artist_save", body)

    @r.post("/artist/availability")
    async def availability(body: AvailabilityInput, request: Request): return await run(request, "availability_add", body)

    @r.post("/artist/availability/{window_id}/remove")
    async def availability_remove(window_id: UUID, request: Request): return await run(request, "availability_remove", window_id=window_id)

    @r.get("/artists/{artist_id}/details")
    async def details(artist_id: UUID): return await app.state.database.call("artist_details", {"artist_id": str(artist_id)})

    @r.get("/inquiries")
    async def inquiries(request: Request): return await run(request, "inquiries_list")

    @r.post("/inquiries")
    async def inquiry(body: InquiryInput, request: Request): return await run(request, "inquiry_create", body)

    @r.get("/inquiries/{conversation_id}")
    async def conversation(conversation_id: UUID, request: Request): return await run(request, "conversation", conversation_id=conversation_id)

    @r.post("/inquiries/{conversation_id}/messages")
    async def message(conversation_id: UUID, body: MessageInput, request: Request): return await run(request, "message_send", body, conversation_id=conversation_id)

    @r.post("/inquiries/{conversation_id}/quotes")
    async def quote(conversation_id: UUID, body: QuoteInput, request: Request): return await run(request, "quote_create", body, conversation_id=conversation_id)

    @r.post("/quotes/{quote_id}/accept")
    async def accept(quote_id: UUID, body: AcceptInput, request: Request): return await run(request, "quote_accept", body, quote_id=quote_id)

    @r.get("/bookings")
    async def bookings(request: Request): return await run(request, "bookings_list")

    @r.post("/bookings/{booking_id}/complete")
    async def complete(booking_id: UUID, request: Request): return await run(request, "booking_complete", booking_id=booking_id)

    @r.post("/bookings/{booking_id}/reviews")
    async def review(booking_id: UUID, body: ReviewInput, request: Request): return await run(request, "review_create", body, booking_id=booking_id)

    @r.get("/notifications")
    async def notifications(request: Request): return await run(request, "notifications_list")

    @r.post("/notifications/{notification_id}/read")
    async def notification_read(notification_id: UUID, request: Request): return await run(request, "notification_read", notification_id=notification_id)

    @r.get("/admin")
    async def admin(request: Request): return await run(request, "admin_list")

    @r.post("/admin/artists/{artist_id}")
    async def moderate(artist_id: UUID, body: ModerationInput, request: Request): return await run(request, "artist_moderate", body, artist_id=artist_id)

    @r.post("/admin/users/{user_id}")
    async def moderate_user(user_id: UUID, body: UserModeration, request: Request): return await run(request, "user_moderate", body, user_id=user_id)

    @r.post("/admin/reviews/{review_id}")
    async def moderate_review(review_id: UUID, body: ModerationInput, request: Request): return await run(request, "review_moderate", body, review_id=review_id)

    app.include_router(r)
