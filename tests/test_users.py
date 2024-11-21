import pytest
import pytest_asyncio

from pangloss.database import Database
from pangloss.model_config.model_manager import ModelManager
from pangloss.users import create_user, UserInDB, authenticate_user


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


@pytest_asyncio.fixture(scope="function")
async def clear_database():
    # await Database.dangerously_clear_database()
    try:
        yield
    except Exception:
        pass

    await Database.dangerously_clear_database()


@pytest.mark.asyncio
async def test_create_user(clear_database):
    await create_user("johnsmith", "john@smith.com", "any", admin=True)

    user = await UserInDB.get(username="johnsmith")
    assert user
    assert user.username == "johnsmith"


@pytest.mark.asyncio
async def test_authenticate_user(clear_database):
    await create_user("johnsmith", "john@smith.com", "any", admin=True)

    authenticated_user = await authenticate_user("johnsmith", "any")
    assert authenticated_user
    assert authenticated_user.username == "johnsmith"
