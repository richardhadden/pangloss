from __future__ import annotations

import datetime
import typing
import uuid

import pytest
import pytest_asyncio

from pangloss.cypher.create import build_create_node_query_object
from pangloss.database import Database
from pangloss.model_config.models_base import Embedded, ReifiedRelationNode
from pangloss.models import BaseNode, RelationConfig, EdgeModel, ReifiedRelation
from pangloss.model_config.model_manager import ModelManager


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

    assert order_from_db.thing_ordered[0].type == "Singing"
    assert order_from_db.thing_ordered[0].label == "John Smith sings"
    singing_uuid = order_from_db.thing_ordered[0].uuid
    assert singing_uuid

    assert order_from_db.thing_ordered[0].singing_by[0].type == "Person"
    assert order_from_db.thing_ordered[0].singing_by[0].uuid == person_in_db.uuid
    assert order_from_db.thing_ordered[0].singing_by[0].label == "John Smith"

    singing_from_db = await Singing.get_view(uuid=singing_uuid)
    assert singing_from_db
    assert singing_from_db.created_by == "DefaultUser"


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_reified_relation(clear_database):
    class Certainty(EdgeModel):
        certainty: int

    TIdentification = typing.TypeVar("TIdentification")

    class Identification(ReifiedRelation[TIdentification]):
        target: typing.Annotated[
            TIdentification,
            RelationConfig(reverse_name="is_target_of", edge_model=Certainty),
        ]

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        involves_person: typing.Annotated[
            Identification[Person], RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    person = Person(type="Person", label="John Smith")
    person_in_db = await person.create()

    event = Event(
        type="Event",
        label="An Event",
        involves_person=[
            {
                "type": "Identification[test_create_with_reified_relation.<locals>.Person]",
                "target": [
                    {
                        "edge_properties": {"certainty": 1},
                        "uuid": person_in_db.uuid,
                        "type": "Person",
                    }
                ],
            }
        ],
    )

    event_in_db = await event.create()
    assert event_in_db

    event_from_db = await event.get_view(uuid=event_in_db.uuid)
    assert event_from_db

    assert event_from_db.type == "Event"
    assert event_from_db.label == "An Event"
    assert (
        event_from_db.involves_person[0].type
        == "Identification[test_create_with_reified_relation.<locals>.Person]"
    )
    assert event_from_db.involves_person[0].uuid
    assert event_from_db.involves_person[0].target[0].type == "Person"
    assert event_from_db.involves_person[0].target[0].uuid
    assert event_from_db.involves_person[0].target[0].label == "John Smith"
    assert event_from_db.involves_person[0].target[0].edge_properties.certainty == 1


@typing.no_type_check
@pytest.mark.asyncio
async def test_write_embedded_nodes(clear_database):
    class Date(BaseNode):
        precise_date: datetime.date

    class Event(BaseNode):
        when: Embedded[Date]

    ModelManager.initialise_models(_defined_in_test=True)

    event = Event(
        type="Event",
        label="An Event",
        when=[{"type": "Date", "precise_date": datetime.date.today()}],
    )

    event_in_db = await event.create()
    assert event_in_db

    event_from_db = await Event.get_view(uuid=event_in_db.uuid)
    assert event_from_db

    assert event_from_db.when[0].precise_date == datetime.date.today()


@typing.no_type_check
@pytest.mark.asyncio
# async def test_speed():
async def speed():
    """Random speed check —— turned off for now"""

    class Certainty(EdgeModel):
        certainty: int

    TIdentification = typing.TypeVar("TIdentification")

    class Identification(ReifiedRelation[TIdentification]):
        target: typing.Annotated[
            TIdentification,
            RelationConfig(reverse_name="is_target_of", edge_model=Certainty),
        ]

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        involves_person: typing.Annotated[
            Identification[Person], RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    persons = []
    for i in range(100):
        person = Person(type="Person", label=f"John Smith {i}")
        person_in_db = await person.create()
        persons.append(person_in_db)

    event = Event(
        type="Event",
        label="An Event",
        involves_person=[
            {
                "type": "Identification[test_speed.<locals>.Person]",
                "target": [
                    {
                        "edge_properties": {"certainty": i},
                        "uuid": person.uuid,
                        "type": "Person",
                    }
                ],
            }
            for i, person in enumerate(persons)
        ],
    )
    import time

    start = time.time()
    event_in_db = await event.create()
    assert (time.time() - start) < 5

    start = time.time()
    await event.get_view(uuid=event_in_db.uuid)
    assert (time.time() - start) < 0.05


@typing.no_type_check
@pytest.mark.asyncio
async def test_create_with_reified_node(clear_database):
    class Person(BaseNode):
        pass

    class IdentificationCertainty(EdgeModel):
        certainty: int

    IdentificationTargetT = typing.TypeVar("IdentificationTargetT")

    class Identification(ReifiedRelation[IdentificationTargetT]):
        target: typing.Annotated[
            IdentificationTargetT,
            RelationConfig(
                reverse_name="is_target_of", edge_model=IdentificationCertainty
            ),
        ]

    class WithProxyActor[T](ReifiedRelationNode[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
        proxy: typing.Annotated[T, RelationConfig(reverse_name="acts_as_proxy_in")]

    class Event(BaseNode):
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    person1 = Person(type="Person", label="JohnSmith")
    person1_in_db = await person1.create()

    person2 = Person(type="Person", label="TobyJones")
    person2_in_db = await person2.create()

    event = Event(
        type="Event",
        label="An Event",
        carried_out_by=[
            {
                "label": "Jones acts as proxy for Smith",
                "type": "WithProxyActor[Identification[test_create_with_reified_node.<locals>.Person]]",
                "target": [
                    {
                        "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": person1_in_db.uuid,
                            }
                        ],
                    }
                ],
                "proxy": [
                    {
                        "type": "Identification[test_create_with_reified_node.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": person2_in_db.uuid,
                            }
                        ],
                    }
                ],
            },
        ],
    )

    event_in_db = await event.create()

    event_from_db = await Event.get_view(uuid=event_in_db.uuid)

    assert event_from_db.label == "An Event"
    assert event_from_db.carried_out_by

    assert event_from_db.carried_out_by[0].label == "Jones acts as proxy for Smith"
    assert event_from_db.carried_out_by[0].target[0].target[0].label == "JohnSmith"
    assert (
        event_from_db.carried_out_by[0].target[0].target[0].uuid == person1_in_db.uuid
    )
    assert (
        event_from_db.carried_out_by[0].target[0].target[0].edge_properties.certainty
        == 1
    )
    assert event_from_db.carried_out_by[0].proxy[0].target[0].label == "TobyJones"
    assert event_from_db.carried_out_by[0].proxy[0].target[0].uuid == person2_in_db.uuid
    assert (
        event_from_db.carried_out_by[0].proxy[0].target[0].edge_properties.certainty
        == 1
    )
