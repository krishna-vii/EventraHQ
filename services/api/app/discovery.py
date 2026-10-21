"""Deterministic eligibility precedes ranking and AI. Dates never use preview flags."""
from datetime import date


async def eligible(catalogue, *, search="", category=None, city="", genre="", event_type="", max_price_paise=None, event_date: date | None = None):
    if catalogue.mode == "database" and "all" not in catalogue.__dict__:
        items, _ = await catalogue.search(search=search, category=category, city=city, genre=genre, event_type=event_type, max_price_paise=max_price_paise, event_date=event_date, page_size=200)
        return items
    items = await catalogue.all()
    if search.strip():
        needle = search.strip().casefold()
        items = [a for a in items if needle in " ".join([a.name, a.category, a.city, a.tagline, *a.tags]).casefold()]
    if category:
        items = [a for a in items if a.category == category]
    if city.strip():
        items = [a for a in items if a.city.casefold() == city.strip().casefold()]
    if genre.strip():
        items = [a for a in items if any(genre.strip().casefold() in tag.casefold() for tag in a.tags)]
    if event_type:
        items = [a for a in items if event_type in a.event_types]
    if max_price_paise is not None:
        items = [a for a in items if a.price_paise <= max_price_paise]
    if event_date:
        ids = await catalogue.available_on(event_date)
        items = [a for a in items if str(a.id) in ids]
    return items
