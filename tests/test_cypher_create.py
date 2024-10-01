from __future__ import annotations

import typing
import uuid

import pytest
import pytest_asyncio

from pangloss.cypher.create import build_create_node_query_object
from pangloss.database import Database
from pangloss.models import BaseNode, RelationConfig, EdgeModel
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

    query_object, _ = build_create_node_query_object(thing, head_node=True)

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
    # assert param_object["created_by"] == "DefaultUser"
    # assert isinstance(param_object["created_when"], datetime.datetime)
    # assert param_object["modified_by"] == "DefaultUser"
    # assert isinstance(param_object["modified_when"], datetime.datetime)


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


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_relation(clear_database):
    class Event(BaseNode):
        name: str
        concerns_person: typing.Annotated[
            Person, RelationConfig(reverse_name="is_concerned_in")
        ]

    class Person(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    person = Person(type="Person", label="John Smith")
    person_in_db = await person.create()

    person_from_db = await Person.get_view(uuid=person_in_db.uuid)
    assert person_from_db

    event = Event(
        type="Event",
        label="An Event",
        name="An Event",
        concerns_person=[{"type": "Person", "uuid": person_in_db.uuid}],
    )

    event_in_db = await event.create()
    assert event_in_db.uuid
    assert event_in_db.type == "Event"
    assert event_in_db.label == "An Event"

    # Now get the view from the DB to check we have relation
    event_from_db = await Event.get_view(uuid=event_in_db.uuid)

    assert event_from_db.name == "An Event"
    assert event_from_db.concerns_person == [
        Person.ReferenceView(
            **{"type": "Person", "uuid": person_in_db.uuid, "label": "John Smith"}
        )
    ]


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_relation_edge_model(clear_database):
    class InvolvementType(EdgeModel):
        type_of_involvement: str

    class Event(BaseNode):
        name: str
        concerns_person: typing.Annotated[
            Person,
            RelationConfig(reverse_name="is_concerned_in", edge_model=InvolvementType),
        ]

    class Person(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    person = Person(type="Person", label="John Smith")
    person_in_db = await person.create()

    event = Event(
        type="Event",
        label="An Event",
        name="An Event",
        concerns_person=[
            {
                "type": "Person",
                "uuid": person_in_db.uuid,
                "edge_properties": {"type_of_involvement": "Bad"},
            }
        ],
    )

    event_in_db = await event.create()
    assert event_in_db.uuid
    assert event_in_db.type == "Event"
    assert event_in_db.label == "An Event"

    # Now get the view from the DB to check we have relation
    event_from_db = await Event.get_view(uuid=event_in_db.uuid)

    assert event_from_db.name == "An Event"
    assert event_from_db.concerns_person[0]
    concerns_person = event_from_db.concerns_person[0]
    assert concerns_person.edge_properties.type_of_involvement == "Bad"


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_create_inline():
    class Person(BaseNode):
        pass

    class Order(BaseNode):
        thing_ordered: typing.Annotated[
            Singing, RelationConfig(reverse_name="ordered_in", create_inline=True)
        ]

    class Singing(BaseNode):
        singing_by: typing.Annotated[Person, RelationConfig(reverse_name="sung_by")]

    ModelManager.initialise_models(_defined_in_test=True)

    person = Person(type="Person", label="John Smith")
    person_in_db = await person.create()

    order = Order(
        type="Order",
        label="John Smith ordered to sing",
        thing_ordered=[
            {
                "type": "Singing",
                "label": "John Smith sings",
                "singing_by": [{"type": "Person", "uuid": person_in_db.uuid}],
            }
        ],
    )

    order_in_db = await order.create()
    assert order_in_db.label == "John Smith ordered to sing"

    order_from_db = await order.get_view(uuid=order_in_db.uuid)


[
    {
        "created_by": "DefaultUser",
        "_type": "BaseNode:Order:HeadNode",
        "thing_ordered": [
            {
                "_type": "BaseNode:Singing:CreateInline:ReadInline",
                "thing_ordered._id": 11,
                "_head_uuid": "066fbf38-3c41-79b0-8000-69aaf64fb1a5",
                "thing_ordered._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:11",
                "_id": 25,
                "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:25",
                "label": "John Smith sings",
                "uuid": "066fbf38-3c42-7081-8000-ef760a7bb5a5",
                "type": "Singing",
                "singing_by": [
                    {
                        "_type": "Person:BaseNode:HeadNode",
                        "singing_by._id": 10,
                        "_id": 37,
                        "singing_by._elementId": "5:945401ed-5520-433b-96f1-e880b23ad925:10",
                        "singing_by.reverse_relation_labels": ["sung_by"],
                        "singing_by.relation_labels": ["singing_by"],
                        "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:37",
                        "label": "John Smith",
                        "uuid": "066fbf38-3ba6-7d26-8000-518420176fd2",
                        "type": "Person",
                    }
                ],
            }
        ],
        "created_when": neo4j.time.DateTime(
            2024, 10, 1, 13, 5, 7, 815721390, tzinfo="<UTC>"
        ),
        "_id": 23,
        "modified_by": None,
        "_elementId": "4:945401ed-5520-433b-96f1-e880b23ad925:23",
        "label": "John Smith ordered to sing",
        "uuid": "066fbf38-3c41-79b0-8000-69aaf64fb1a5",
        "modified_when": None,
        "type": "Order",
    }
]
