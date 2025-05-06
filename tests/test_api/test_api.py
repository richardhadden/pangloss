import asyncio
import datetime
import typing

import httpx
import pytest

from pangloss.users.utils import create_user
from tests.test_api.test_app.models import MyModel


@pytest.mark.asyncio
async def test_get_docs(server):
    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/docs")
        assert response.status_code == 200
        assert "Swagger UI" in response.text


@pytest.mark.asyncio
async def test_docs_endpoints(server):
    async with httpx.AsyncClient(base_url=server.url) as client:
        response = await client.get("/openapi.json")
        assert response.status_code == 200
        docs = response.json()
        assert docs
        assert "/api/MyModel/" in docs["paths"]

        assert docs["paths"]["/api/MyModel/"]["get"]["operationId"] == "MyModelIndex"
        assert docs["paths"]["/api/MyModel/{id}"]["get"]["operationId"] == "MyModelGet"
        assert (
            docs["paths"]["/api/MyModel/new"]["post"]["operationId"] == "MyModelCreate"
        )
        assert (
            docs["paths"]["/api/MyModel/{id}/edit"]["get"]["operationId"]
            == "MyModelEditGet"
        )
        assert (
            docs["paths"]["/api/MyModel/{id}/edit"]["patch"]["operationId"]
            == "MyModelEditPatch"
        )


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


async def user():
    await create_user(
        username="testuser",
        email="none@none.net",
        password="testpassword",
        admin=True,
    )


@pytest.mark.asyncio
async def test_get_user_token(server):
    await user()

    async with httpx.AsyncClient(base_url=server.url) as client:
        # Test with no user fails
        response = await client.post(
            "api/users/token",
            json={"username": "nonesuch", "password": "none"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data == {"detail": {"message": "Bad credentials"}}

    async with httpx.AsyncClient(base_url=server.url) as client:
        # Test with wrong password fails
        response = await client.post(
            "api/users/token",
            json={"username": "testuser", "password": "none"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data == {"detail": {"message": "Bad credentials"}}

    async with httpx.AsyncClient(base_url=server.url) as client:
        # Test with real password works
        response = await client.post(
            "api/users/token",
            json={"username": "testuser", "password": "testpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data


@typing.no_type_check
@pytest.mark.asyncio
async def test_create(server):
    await user()

    # Check we cannot create when not logged in
    async with httpx.AsyncClient(base_url=server.url) as client:
        result = await client.post(
            "api/MyModel/new",
            json={"label": "Tomato", "name": "Tomato", "type": "MyModel"},
        )

        assert result.status_code == 401

    # Do log in
    async with httpx.AsyncClient(base_url=server.url) as client:
        # Test with real password works
        response = await client.post(
            "api/users/token",
            json={"username": "testuser", "password": "testpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    # Now check we can create with authorisation token
    async with httpx.AsyncClient(
        base_url=server.url,
    ) as client:
        result = await client.post(
            "api/MyModel/new",
            json={
                "label": "Gherkin",
                "name": "Gherkin",
                "type": "MyModel",
            },
            headers={
                "Authorization": f"Bearer {data['access_token']}",
                "Content-Type": "application/json",
            },
        )

        assert result.status_code == 200

    data = result.json()
    gherkin_id = data["id"]
    assert gherkin_id

    # Check the created item is in the database
    gherkin_from_db = await MyModel.get_view(id=gherkin_id)
    assert gherkin_from_db
    assert gherkin_from_db.id == gherkin_id
    assert gherkin_from_db.label == "Gherkin"
    assert gherkin_from_db.name == "Gherkin"
    assert gherkin_from_db.created_by == "testuser"
    assert gherkin_from_db.created_when < datetime.datetime.now(datetime.timezone.utc)

    # And check we can get the same item via the API
    async with httpx.AsyncClient(
        base_url=server.url,
    ) as client:
        result = await client.get(f"/api/MyModel/{gherkin_id}")
        assert result.status_code == 200
        data = result.json()
        assert data
        assert data["id"] == gherkin_id


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_deferred(server):
    await user()

    # Do log in
    async with httpx.AsyncClient(base_url=server.url) as client:
        # Test with real password works
        response = await client.post(
            "api/users/token",
            json={"username": "testuser", "password": "testpassword"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
