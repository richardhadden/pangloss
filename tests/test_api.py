import asyncio
import typing
import uuid

import httpx
import pytest
import pytest_asyncio
from pydantic import AnyHttpUrl

from pangloss.application import get_application
from pangloss.database import Database
from pangloss.model_config.model_manager import ModelManager
from pangloss.settings import BaseSettings
from pangloss.users import UserInDB, create_user


class Settings(BaseSettings):
    PROJECT_NAME: str = "MyTestApp"
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    DB_URL: str = "bolt://localhost:7688"
    DB_USER: str = "neo4j"
    DB_PASSWORD: str = "password"
    DB_DATABASE_NAME: str = "neo4j"

    INSTALLED_APPS: list[str] = ["pangloss", "tests.test_app"]
    authjwt_secret_key: str = "SECRET"

    INTERFACE_LANGUAGES: list[str] = ["en"]


settings = Settings()
application = get_application(settings)


@pytest_asyncio.fixture(scope="function")
async def clear_database():
    # await Database.dangerously_clear_database()
    try:
        yield
    except Exception:
        pass

    await Database.dangerously_clear_database()


@pytest_asyncio.fixture()
async def client() -> typing.AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(
        app=application, base_url="http://test", follow_redirects=True
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_sanity(client):
    """Make sure client is fired up and returning docs; and that application setup runs
    and imports the test_application models"""
    response = await client.get("/docs")
    assert response.status_code == 200

    assert (
        ModelManager.registered_models != []
    )  # Quick test to make sure there are some models


"""
ZOTERO_ENTRY_UID = uuid.uuid4()


def not_none[T](obj: typing.Optional[T]) -> T:
    assert obj is not None
    return obj


@pytest_asyncio.fixture(scope="function")
async def zotero_entry() -> typing.AsyncIterator[ZoteroEntry]:
    zotero_entry = ZoteroEntry(
        uid=ZOTERO_ENTRY_UID, label="A Test Zotero Entry", real_type="ZoteroEntry"
    )
    await zotero_entry.create()
    yield zotero_entry
    await Database.dangerously_clear_database()
"""

USERNAME = "jsmith"
EMAIL = "jsmith@jsmith.net"
PASSWORD = "password"


@pytest_asyncio.fixture
async def user():
    yield (
        await create_user(
            username=USERNAME, email=EMAIL, password=PASSWORD, admin=False
        )
    )
    await Database.dangerously_clear_database()


@pytest.mark.asyncio
async def test_user_fixture(user: str):
    user_in_db = await UserInDB.get(username=USERNAME)
    assert user_in_db
    assert user_in_db.username == user


@pytest.mark.asyncio
async def test_login(user, client: httpx.AsyncClient):
    response = await client.post("/api/users/login")
    # Test not providing username or password returns
    # status code for unprocessable entity
    assert response.status_code == 422

    response = await client.post(
        "/api/users/login", data={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    assert response.cookies["access_token"]
    assert response.cookies["logged_in_user_name"]


@pytest.mark.asyncio
async def test_create_person_when_not_logged_in_raises_401(client: httpx.AsyncClient):
    response = await client.post(
        "/api/Person/new",
        data={
            "label": "Toby Jones",
            "type": "Person",
            "name": "Toby Jones",
        },
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}


@pytest_asyncio.fixture
async def logged_in_client(user, client):
    response = await client.post(
        "/api/users/login", data={"username": USERNAME, "password": PASSWORD}
    )
    assert response.status_code == 200
    async with httpx.AsyncClient(
        app=application,
        base_url="http://test",
        cookies=response.cookies,
        follow_redirects=True,
    ) as async_client:
        yield async_client


@pytest.mark.asyncio
async def test_create_and_get_person(logged_in_client: httpx.AsyncClient):
    create_resp = await logged_in_client.post(
        "/api/Person/new",
        json={
            "label": "Toby Jones",
            "type": "Person",
            "name": "Toby Jones",
        },
    )

    assert create_resp.status_code == 200
    create_resp_data = create_resp.json()
    assert create_resp_data["type"] == "Person"
    assert create_resp_data["label"] == "Toby Jones"
    assert create_resp_data["uuid"]

    get_resp = await logged_in_client.get(f"/api/Person/{create_resp_data["uuid"]}")
    get_resp_data = get_resp.json()
    assert get_resp_data["uuid"] == create_resp_data["uuid"]
    assert get_resp_data["createdBy"] == "jsmith"


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_person(logged_in_client: httpx.AsyncClient):
    create_resp = await logged_in_client.post(
        "/api/Person/new",
        json={
            "label": "Toby Jones",
            "type": "Person",
            "name": "Toby Jones",
        },
    )

    assert create_resp.status_code == 200
    create_resp_data = create_resp.json()

    edit_resp = await logged_in_client.get(
        f"/api/Person/{create_resp_data["uuid"]}/edit"
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()

    person_edit = edit_resp.json()
    person_edit["label"] = "Toby Jones Updated"

    update_resp = await logged_in_client.patch(
        f"/api/Person/{create_resp_data["uuid"]}/edit", json=person_edit
    )
    assert update_resp.status_code == 200
    assert update_resp.json() == {"detail": "Update successful"}

    get_resp = await logged_in_client.get(
        f"/api/Person/{create_resp_data["uuid"]}",
    )

    get_resp_data = get_resp.json()
    assert get_resp_data["label"] == "Toby Jones Updated"
    assert get_resp_data["modifiedBy"] == "jsmith"
    assert get_resp_data["modifiedWhen"]


@pytest_asyncio.fixture
async def created_person(logged_in_client: httpx.AsyncClient) -> dict:
    create_resp = await logged_in_client.post(
        "/api/Person/new",
        json={
            "label": "Toby Jones",
            "type": "Person",
            "name": "Toby Jones",
        },
    )

    assert create_resp.status_code == 200
    create_resp_data = create_resp.json()
    return create_resp_data


@typing.no_type_check
@pytest.mark.asyncio
async def test_list_request(logged_in_client: httpx.AsyncClient, created_person):
    await asyncio.sleep(1)  # Stick a delay here so the index has a change to refresh
    # Can probably get away with less than a second (~0.08 seems ok) but
    # a second won't hurt
    response = await logged_in_client.get("/api/Person/")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert uuid.UUID(data["results"][0]["uuid"]) == uuid.UUID(created_person["uuid"])


@typing.no_type_check
@pytest.mark.asyncio
async def test_list_request_with_full_text_query(logged_in_client: httpx.AsyncClient):
    create_resp = await logged_in_client.post(
        "/api/Person/new",
        json={
            "label": "Toby Jones",
            "type": "Person",
            "name": "Toby Jones",
        },
    )

    assert create_resp.status_code == 200
    create_resp_data = create_resp.json()
    await asyncio.sleep(0.08)  # Stick a delay here so the index has a change to refresh
    # Can probably get away with less than a second (~0.08 seems ok) but
    # a second won't hurt
    response = await logged_in_client.get("/api/Person/?q=toby")

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert uuid.UUID(data["results"][0]["uuid"]) == uuid.UUID(create_resp_data["uuid"])


'''
@pytest.mark.asyncio
async def test_zotero_entry_written(zotero_entry: ZoteroEntry):
    """Tests the zotero_entry fixture"""
    z = await ZoteroEntry.get_view(uid=not_none(zotero_entry.uid))
    assert z.uid == zotero_entry.uid


""" # Changed viewing to be possible without login by default
# Need to implement some kind of permissions model and then test this
# properly
@pytest.mark.asyncio
async def test_api_get_zotero_entry_when_unauthorised_is_wrong(
    client: httpx.AsyncClient, zotero_entry
):
    response = await client.get(
        f"/api/ZoteroEntry/{ZOTERO_ENTRY_UID}", follow_redirects=True
    )
    assert response.status_code == 401
    data = response.json()

    assert data == {"detail": "Not authenticated"} """


@pytest.mark.asyncio
async def test_api_get_zotero_entry_when_logged_in(
    logged_in_client: httpx.AsyncClient, zotero_entry: ZoteroEntry
):
    response = await logged_in_client.get(f"/api/ZoteroEntry/{ZOTERO_ENTRY_UID}")
    assert response.status_code == 200
    data = response.json()
    assert uuid.UUID(data["uid"]) == zotero_entry.uid
    assert data["realType"] == "ZoteroEntry"
    assert data["label"] == "A Test Zotero Entry"


@pytest.mark.asyncio
async def test_list_item_with_api(client: httpx.AsyncClient, zotero_entry: ZoteroEntry):
    response = await client.get("/api/ZoteroEntry", follow_redirects=True)
    assert response.status_code == 200
    data = response.json()
    assert data

    assert len(data["results"]) == 1
    assert data["count"] == 1
    assert data["nextUrl"] is None
    assert data["nextPage"] is None
    assert data["previousPage"] is None
    assert data["previousUrl"] is None
    item = data["results"][0]

    assert uuid.UUID(item["uid"]) == zotero_entry.uid
    assert item["realType"] == "ZoteroEntry"
    assert item["label"] == "A Test Zotero Entry"


@pytest.mark.asyncio
async def test_create_person_when_not_logged_in_raises_401(client: httpx.AsyncClient):
    response = await client.post(
        "/api/Person/new",
        data={
            "label": "Toby Jones",
            "realType": "Person",
        },
    )
    assert response.status_code == 401


@pytest_asyncio.fixture
async def person_created_response(logged_in_client: httpx.AsyncClient):
    response = await logged_in_client.post(
        "/api/Person/new",
        json={
            "label": "Toby Jones",
            "realType": "Person",
        },
    )
    assert response.status_code == 200
    data = response.json()
    yield data
    await Database.dangerously_clear_database()


@pytest.mark.asyncio
async def test_person_fixture(person_created_response):
    data = person_created_response
    assert uuid.UUID(data["uid"])
    assert data["realType"] == "Person"
    assert data["label"] == "Toby Jones"


@pytest.mark.asyncio
async def test_create_person_when_logged_in_works(logged_in_client: httpx.AsyncClient):
    response = await logged_in_client.post(
        "/api/Person/new",
        json={
            "label": "Toby Jones",
            "realType": "Person",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert uuid.UUID(data["uid"])
    assert data["realType"] == "Person"
    assert data["label"] == "Toby Jones"


@pytest.mark.asyncio
async def test_get_created_person(
    logged_in_client: httpx.AsyncClient, person_created_response
):
    response = await logged_in_client.get(
        f"/api/Person/{person_created_response['uid']}"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["carriedOutActivity"] is None
    assert data["hasBirthEvent"] is None
    assert data["hasDeathEvent"] is None
    assert data["isSubjectOfStatement"] is None
    assert data["label"] == "Toby Jones"
    assert data["realType"] == "Person"
    assert data["uid"] == person_created_response["uid"]


@pytest.mark.asyncio
async def test_create_factoid(
    logged_in_client: httpx.AsyncClient,
    person_created_response,
    zotero_entry: ZoteroEntry,
):
    response = await logged_in_client.post(
        "/api/Factoid/new",
        json={
            "label": "Toby Jones is born",
            "realType": "Factoid",
            "citation": [
                {
                    "realType": "Citation",
                    "reference": [
                        {
                            "uid": str(zotero_entry.uid),
                            "label": zotero_entry.label,
                            "realType": "ZoteroEntry",
                        }
                    ],
                    "scope": "Page 94",
                }
            ],
            "statements": [
                {
                    "label": "Birth of Toby Jones",
                    "realType": "Birth",
                    "personBorn": [
                        {
                            "uid": person_created_response["uid"],
                            "label": person_created_response["label"],
                            "realType": "Person",
                        }
                    ],
                    "when": "1998-01-01",
                }
            ],
        },
    )

    assert response.status_code == 200

    data = response.json()
    assert uuid.UUID(data["uid"])
    assert data["label"] == "Toby Jones is born"

    # Now check it's in the database!
    f = await Factoid.View.get(uid=data["uid"])
    assert f.uid == uuid.UUID(data["uid"])

    # Now get it from the API
    response = await logged_in_client.get(f"/api/Factoid/{f.uid}")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_query(logged_in_client: httpx.AsyncClient, zotero_entry):
    await asyncio.sleep(1)  # Stick a delay here so the index has a change to refresh
    # Can probably get away with less than a second (~0.08 seems ok) but
    # a second won't hurt
    response = await logged_in_client.get("/api/ZoteroEntry/?q=entry")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert uuid.UUID(data["results"][0]["uid"]) == zotero_entry.uid
'''
