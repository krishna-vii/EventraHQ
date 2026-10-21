from typing import Annotated, Literal
from uuid import UUID
from datetime import date

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator


Category = Literal["Live band", "DJ", "Vocalist", "Instrumental"]
MAX_EVIDENCE_ARTISTS = 8


class Artist(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: UUID
    slug: str
    name: str
    category: Category
    city: str
    price_paise: Annotated[int, Field(ge=0)]
    rating: Annotated[float, Field(ge=0, le=5)]
    review_count: Annotated[int, Field(ge=0)]
    tagline: str
    description: str
    tags: list[str]
    accent: Literal["teal", "violet", "blue", "amber"]
    available: bool
    is_fixture: bool = True
    photo_path: str | None = None
    event_types: list[str] = Field(default_factory=list)


class ArtistList(BaseModel):
    items: list[Artist]
    total: int
    mode: Literal["fixtures", "database"]
    page: int = 1
    page_size: int = 24


class AssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief: Annotated[StrictStr, Field(min_length=8, max_length=1200)]
    artist_ids: Annotated[list[UUID], Field(max_length=MAX_EVIDENCE_ARTISTS)] = Field(default_factory=list)
    city: str = Field(default="", max_length=80)
    event_type: str = Field(default="", max_length=80)
    max_price_paise: int | None = Field(default=None, ge=0, le=1000000000)
    event_date: date | None = None

    @field_validator("brief")
    @classmethod
    def trim_brief(cls, value: str) -> str:
        value = value.strip()
        if len(value) < 8:
            raise ValueError("Describe your event in at least 8 characters.")
        # Bound bytes as well as code points for the compact model context.
        if len(value.encode("utf-8")) > 1600:
            raise ValueError("Shorten the brief to at most 1600 UTF-8 bytes for the local model.")
        return value

    @field_validator("artist_ids")
    @classmethod
    def unique_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("Artist IDs must be unique.")
        return value


class AssistantAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: Annotated[StrictStr, Field(min_length=1, max_length=1800)]
    artist_ids: Annotated[list[UUID], Field(max_length=MAX_EVIDENCE_ARTISTS)]

    @field_validator("message")
    @classmethod
    def nonempty_message(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("The model returned an empty message.")
        return value.strip()
