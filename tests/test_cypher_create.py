import datetime
import typing
import uuid

import pytest
import pytest_asyncio

from pangloss.cypher.create import build_create_node_query_object
from pangloss.database import Database
from pangloss.models import BaseNode
from pangloss.model_config.model_manager import ModelManager


@pytest_asyncio.fixture(scope="function")
async def clear_database():
    # await Database.dangerously_clear_database()
    try:
        yield
    except Exception:
        pass

    await Database.dangerously_clear_database()


def test_build_basic_properties_query():
    class Thing(BaseNode):
        name: str
        age: int

    ModelManager.initialise_models(_defined_in_test=True)

    thing = Thing(type="Thing", label="A Thing", name="A Thing", age=1)

    query_object = build_create_node_query_object(thing, start_node=True)

    cqs = query_object.create_query_strings[0]

    assert query_object.return_identifier

    assert f"CREATE ({query_object.return_identifier}" in cqs
    assert ":BaseNode" in cqs
    assert ":Thing" in cqs

    assert "{uuid: " in cqs

    set_param_key = list(query_object.query_params.keys())[0]
    assert f"SET {query_object.return_identifier} = ${set_param_key}"

    assert f"RETURN {query_object.return_identifier}" in query_object.to_query_string()

    param_object = query_object.query_params[set_param_key]

    assert param_object["age"] == 1
    assert param_object["label"] == "A Thing"
    assert param_object["name"] == "A Thing"
    assert param_object["type"] == "Thing"
    assert param_object["created_by"] == "DefaultUser"
    assert isinstance(param_object["created_when"], datetime.datetime)
    assert param_object["modified_by"] == "DefaultUser"
    assert isinstance(param_object["modified_when"], datetime.datetime)


@typing.no_type_check
@pytest.mark.asyncio
async def test_basic_create_on_model():
    class Thing(BaseNode):
        name: str
        age: int

    ModelManager.initialise_models(_defined_in_test=True)

    thing = Thing(type="Thing", label="A Thing", name="A Thing", age=1)

    thing_in_db = await thing.create()

    assert thing_in_db

    assert thing_in_db.type == "Thing"
    assert thing_in_db.label == "A Thing"
    assert isinstance(thing_in_db.uuid, uuid.UUID)
