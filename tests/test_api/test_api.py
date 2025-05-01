import asyncio

import httpx
import pytest

from tests.test_api.test_app.models import MyModel


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
async def test_list_with_no_data(server):
    # await MyModel(label="Tomato", name="Tomato").create()

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


@pytest.mark.asyncio
async def test_list_with_data(server):
    await MyModel(label="Melon", name="Melon").create()

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1


@pytest.mark.asyncio
async def test_list_with_search(server):
    await MyModel(label="Melon", name="Melon").create()
    await MyModel(label="Tomato", name="Tomato").create()

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2

    # Pause to allow full-text index to update
    await asyncio.sleep(0.5)

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/?q=Melon")
        assert response.status_code == 200
        data = response.json()

    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/api/MyModel/?q=tomato")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
