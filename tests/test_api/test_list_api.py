import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from pangloss.application import get_application
from tests.test_api.conftest import settings


@pytest_asyncio.fixture(loop_scope="module")
async def client():
    from pangloss.neo4j.database import DatabaseUtils

    application = get_application(settings, id(database))

    async with AsyncClient(
        transport=ASGITransport(app=application),
        base_url="http://test",
        follow_redirects=True,
    ) as ac:
        await DatabaseUtils.dangerously_clear_database()
        yield ac


@pytest.mark.asyncio
async def test_get_docs(client) -> None:
    """Base test to ensure the server is started by getting docs"""

    r = await client.get("/docs")
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_api_definition_includes_test_models(client) -> None:
    """Test that the API definition includes models from tests.test_api.test_app"""
    r = await client.get("/openapi.json")
    assert r.status_code == 200

    data = r.json()

    assert "/api/MyModel/" in data["paths"]


@pytest.mark.asyncio
async def test_get_list(client):
    r = await client.get("/api/MyModel/")
    assert r.status_code == 200
