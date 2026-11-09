from uuid import uuid4
import httpx
import pytest
from app.main import create_app
from app.settings import Settings
from app.catalogue import Catalogue, FIXTURES

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_shortlist_filter_runs_before_pagination_and_validates_ids():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(Settings())), base_url='http://127.0.0.1') as client:
        chosen = FIXTURES[-1]
        response = await client.get('/api/v1/artists', params={'artist_ids': str(chosen.id), 'page_size': 1})
        assert response.status_code == 200
        assert response.json()['total'] == 1
        assert response.json()['items'][0]['id'] == str(chosen.id)
        assert (await client.get('/api/v1/artists', params={'artist_ids': str(uuid4())})).json()['items'] == []
        assert (await client.get('/api/v1/artists', params={'artist_ids': 'invalid'})).status_code == 422

@pytest.mark.anyio
async def test_database_detail_lookups_do_not_scan_a_truncated_catalogue():
    catalogue = Catalogue(Settings(database_url='postgresql://eventra_app:test@127.0.0.1:54322/postgres'))
    calls = []
    async def search(**filters):
        calls.append(filters)
        return [FIXTURES[-1]], 1
    async def forbidden():
        pytest.fail('Detail lookup must not scan the capped catalogue')
    catalogue.search = search
    catalogue.all = forbidden
    assert await catalogue.find(FIXTURES[-1].id) == FIXTURES[-1]
    assert await catalogue.find_slug(FIXTURES[-1].slug) == FIXTURES[-1]
    assert calls == [{'artist_ids': [str(FIXTURES[-1].id)], 'page_size': 1}, {'slug': FIXTURES[-1].slug, 'page_size': 1}]
