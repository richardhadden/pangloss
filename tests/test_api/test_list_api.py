import httpx
import pytest

from tests.test_api.conftest import server
from tests.test_api.test_app.models import MyModel

server = server


@pytest.mark.asyncio
async def test_docs(server):
    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "Swagger UI" in response.text


@pytest.mark.asyncio
async def test_docs2(server):
    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        assert "/api/MyModel/" in response.json()["paths"]


@pytest.mark.asyncio
async def test_list(server):
    await MyModel(label="Tomato", name="Tomato").create()

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


@pytest.mark.asyncio
async def test_list2(server):
    await MyModel(label="Melon", name="Melon").create()

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
