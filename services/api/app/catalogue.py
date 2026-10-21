"""Public discovery only. Never grant this adapter business mutation access."""

import asyncio
import json
from pathlib import Path
from uuid import UUID

from pydantic import TypeAdapter

from .models import Artist
from .settings import Settings
import certifi


ARTIST_ADAPTER = TypeAdapter(list[Artist])
FIXTURES = ARTIST_ADAPTER.validate_json((Path(__file__).parent / "data" / "artists.json").read_text(encoding="utf-8"))


class CatalogueUnavailable(Exception):
    pass


class Catalogue:
    def __init__(self, settings: Settings):
        self.database_url = settings.database_url
        self.sslrootcert = settings.database_sslrootcert or certifi.where()
        self.mode = "database" if self.database_url else "fixtures"
        self.include_fixtures = settings.app_env == "local"

    def connect(self, **options):
        import psycopg
        return psycopg.connect(self.database_url.replace("postgresql+psycopg://", "postgresql://", 1), connect_timeout=3,
            prepare_threshold=None, **({"sslrootcert": self.sslrootcert} if "sslmode=verify-full" in self.database_url else {}), **options)

    async def search(self, **filters):
        """SQL pagination/count; never truncate a growing production catalogue in Python."""
        def read():
            from psycopg.rows import dict_row
            values = {"search":"", "category":None, "city":"", "genre":"", "event_type":"", "max_price_paise":None, "event_date":None, "page":1, "page_size":24, "sort":"recommended", **filters, "fixtures": self.include_fixtures}
            values["offset"] = (values["page"]-1)*values["page_size"]
            where = """where (%(fixtures)s or not is_fixture)
              and (%(search)s='' or strpos(lower(name||' '||category||' '||city||' '||tagline||' '||array_to_string(tags,' ')),lower(%(search)s))>0)
              and (%(category)s::text is null or category=%(category)s)
              and (%(city)s='' or lower(city)=lower(%(city)s))
              and (%(genre)s='' or exists(select 1 from unnest(tags) tag where strpos(lower(tag),lower(%(genre)s))>0))
              and (%(event_type)s='' or %(event_type)s=any(event_types))
              and (%(max_price_paise)s::bigint is null or price_paise<=%(max_price_paise)s)
              and (%(event_date)s::date is null or id in(select app.available_artists_on(%(event_date)s::date)))"""
            sort = {"recommended":"name,id", "name":"name,id", "price_low":"price_paise,name,id", "price_high":"price_paise desc,name,id"}[values["sort"]]
            with self.connect(row_factory=dict_row) as conn:
                conn.execute("set transaction isolation level repeatable read read only")
                conn.execute("set local statement_timeout='3000ms'")
                total = conn.execute("select count(*)::int as total from public.artist_marketplace "+where,values).fetchone()["total"]
                rows = conn.execute("select id::text,slug,name,category,city,price_paise::bigint,rating::float8,review_count,tagline,description,tags,accent,available,is_fixture,photo_path,event_types from public.artist_marketplace "+where+" order by "+sort+" limit %(page_size)s offset %(offset)s",values).fetchall()
            return ARTIST_ADAPTER.validate_json(json.dumps(rows)), total
        try:
            return await asyncio.to_thread(read)
        except Exception as error:
            raise CatalogueUnavailable("Database discovery is unavailable. Check connectivity and migrations.") from error

    async def available_on(self, day) -> set[str]:
        if not self.database_url:
            return set()  # Fictional profiles have no verified calendar.
        def read():
            import psycopg
            with self.connect() as conn:
                return {str(r[0]) for r in conn.execute("select * from app.available_artists_on(%s)", (day,))}
        try:
            return await asyncio.to_thread(read)
        except Exception as error:
            raise CatalogueUnavailable("Calendar service is unavailable; no availability has been assumed.") from error

    def _read_database(self) -> list[Artist]:
        import psycopg
        from psycopg.rows import dict_row

        connection_url = self.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
        # One short read-only transaction. No connection is held during inference.
        with self.connect(row_factory=dict_row) as connection:
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute("SET LOCAL statement_timeout = '2000ms'")
            rows = connection.execute(
                "SELECT id::text, slug, name, category, city, price_paise::bigint, "
                "rating::float8, review_count, tagline, description, tags, accent, available, is_fixture, photo_path, event_types "
                "FROM public.artist_marketplace WHERE (%s OR NOT is_fixture) ORDER BY name, id LIMIT 2000", (self.include_fixtures,)
            ).fetchall()
        return ARTIST_ADAPTER.validate_json(json.dumps(rows))

    async def all(self) -> list[Artist]:
        if not self.database_url:
            return [artist.model_copy(deep=True) for artist in FIXTURES]
        try:
            return await asyncio.to_thread(self._read_database)
        except Exception as error:
            # Never expose connection strings, SQL internals or database credentials.
            raise CatalogueUnavailable("The local database catalogue is unavailable. Start the database or explicitly select fixture mode.") from error

    async def find(self, artist_id: UUID) -> Artist | None:
        return next((artist for artist in await self.all() if artist.id == artist_id), None)

    async def health(self) -> dict[str, str]:
        if not self.database_url:
            return {"status": "unavailable", "message": "DATABASE_URL is unset. Read-only fictional fixtures are active; database readiness is not qualified."}
        try:
            await self.all()
            return {"status": "ready", "message": "Local read-only discovery projection is reachable. Auth and transactional flows are not qualified."}
        except CatalogueUnavailable:
            return {"status": "unavailable", "message": "Local database discovery projection is unavailable."}
