from __future__ import annotations

import uuid


import pytest
import pytest_asyncio


from neo4j import Record


from pangloss.database import (
    Database,
    Transaction,
    read_transaction,
    write_transaction,
)
from pangloss.model_config.model_manager import ModelManager


FAKE_UID = uuid.UUID("a19c71f4-a844-458d-82eb-527307f89aab")


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


class ArbitraryDatabaseClass:
    @classmethod
    @write_transaction
    async def write_fake_data(cls, tx: Transaction):
        result = await tx.run(
            "CREATE (new_person:Person {uid: $uid}) RETURN new_person",
            uid=str(FAKE_UID),
        )
        item = await result.single()
        return item

    @classmethod
    @read_transaction
    async def get(
        cls,
        tx: Transaction,
        uid: uuid.UUID,
    ) -> Record | None:
        result = await tx.run(
            "MATCH (new_person {uid: $uid}) RETURN new_person", uid=str(uid)
        )
        item = await result.single()
        return item


@pytest.mark.asyncio
async def test_database_delete():
    await Database.dangerously_clear_database()
    result = await ArbitraryDatabaseClass.write_fake_data()
    assert result
    assert result.data()["new_person"]["uid"] == str(FAKE_UID)

    result = await ArbitraryDatabaseClass.get(FAKE_UID)
    assert result
    assert result.data()["new_person"]["uid"] == str(FAKE_UID)

    await Database.dangerously_clear_database()

    result = await ArbitraryDatabaseClass.get(FAKE_UID)
    assert result is None


@pytest.mark.asyncio
async def test_clear_database_fixture(clear_database):
    result = await ArbitraryDatabaseClass.write_fake_data()
    assert result
    assert result.data()["new_person"]["uid"] == str(FAKE_UID)
