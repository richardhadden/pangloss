from __future__ import annotations

import datetime
import typing

import annotated_types
import pytest
import pytest_asyncio

from pangloss.database import Database
from pangloss.model_config.model_manager import ModelManager
from pangloss.models import (
    BaseNode,
    EdgeModel,
    Embedded,
    ReifiedRelation,
    RelationConfig,
    ReifiedRelationNode,
)


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


@typing.no_type_check
@pytest.mark.asyncio
async def test_get_edit_view():
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
            RelationConfig(reverse_name="carried_out"),
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
                "type": "WithProxyActor[Identification[test_get_edit_view.<locals>.Person]]",
                "target": [
                    {
                        "type": "Identification[test_get_edit_view.<locals>.Person]",
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
                        "type": "Identification[test_get_edit_view.<locals>.Person]",
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

    edit_event_from_db = await Event.get_edit_view(uuid=event_in_db.uuid)

    assert edit_event_from_db.uuid == event_in_db.uuid

    assert (
        edit_event_from_db.carried_out_by[0].target[0].target[0].uuid
        == person1_in_db.uuid
    )


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_with_simple_relation(clear_database):
    class Event(BaseNode):
        event_type: str
        person_involved: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    class Person(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    person1 = Person(type="Person", label="A Person1")
    person1_in_db = await person1.create()

    person2 = Person(type="Person", label="A Person2")
    person2_in_db = await person2.create()

    event = Event(
        type="Event",
        event_type="Party",
        label="An Event",
        person_involved=[{"type": "Person", "uuid": person1_in_db.uuid}],
    )
    event_in_db = await event.create()

    edit_event_from_db = await Event.get_edit_view(uuid=event_in_db.uuid)

    assert edit_event_from_db.person_involved[0].uuid == person1_in_db.uuid

    event_update = Event.EditSet(
        uuid=event_in_db.uuid,
        label=event_in_db.label,
        type="Event",
        event_type="Rave",
        person_involved=[{"type": "Person", "uuid": person2_in_db.uuid}],
    )

    await event_update.update()

    event_from_db = await Event.get_view(uuid=event_in_db.uuid)

    assert event_from_db.event_type == "Rave"

    assert len(event_from_db.person_involved) == 1

    assert event_from_db.person_involved[0].uuid == person2_in_db.uuid


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_reified():
    class Person(BaseNode):
        pass

    class Intermediate[T](ReifiedRelation[T]):
        intermediate_value: str

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Intermediate[Person],
            RelationConfig(reverse_name="is_involved_in"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    person1 = Person(type="Person", label="A Person1")
    person1_created = await person1.create()

    person2 = Person(type="Person", label="A Person2")
    person2_created = await person2.create()

    event = Event(
        type="Event",
        label="An Event",
        person_involved=[
            {
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue1",
                "target": [{"type": "Person", "uuid": person1_created.uuid}],
            }
        ],
    )

    event_created = await event.create()
    event_edit_view = await Event.get_edit_view(uuid=event_created.uuid)

    event_to_update = Event.EditSet(
        uuid=event_created.uuid,
        type="Event",
        label="An Event",
        person_involved=[
            {
                "uuid": event_edit_view.person_involved[0].uuid,
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue2",
                "target": [{"type": "Person", "uuid": person2_created.uuid}],
            }
        ],
    )

    assert event_to_update.person_involved[0].uuid

    assert event_to_update.person_involved[0].intermediate_value == "somevalue2"

    success = await event_to_update.update()
    assert success is True

    event_view = await Event.get_view(uuid=event_created.uuid)
    assert event_view.modified_by == "DefaultUser"

    assert event_view.person_involved[0].intermediate_value == "somevalue2"
    assert event_view.person_involved[0].target[0].uuid == person2_created.uuid
    assert event_view.person_involved[0].target[0].label == "A Person2"

    event_to_update = Event.EditSet(
        uuid=event_created.uuid,
        type="Event",
        label="An Event",
        person_involved=[
            {
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue3",
                "target": [{"type": "Person", "uuid": person2_created.uuid}],
            }
        ],
    )

    success = await event_to_update.update()
    assert success

    event_view2 = await Event.get_view(uuid=event_created.uuid)
    assert event_view2.modified_by == "DefaultUser"
    assert len(event_view2.person_involved) == 1
    assert event_view2.person_involved[0].intermediate_value == "somevalue3"
    assert event_view2.person_involved[0].target[0].uuid == person2_created.uuid

    person3 = Person(type="Person", label="Person3")
    person3_created = await person3.create()

    event_to_update = Event.EditSet(
        uuid=event_created.uuid,
        type="Event",
        label="An Event",
        person_involved=[
            {
                "uuid": event_view2.person_involved[0].uuid,
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue3",
                "target": [{"type": "Person", "uuid": person2_created.uuid}],
            },
            {
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue4",
                "target": [{"type": "Person", "uuid": person3_created.uuid}],
            },
        ],
    )
    success = await event_to_update.update()

    event_view3 = await Event.get_view(uuid=event_created.uuid)
    assert len(event_view3.person_involved) == 2

    assert event_view3.person_involved[0].intermediate_value == "somevalue3"
    assert event_view3.person_involved[0].target[0].uuid == person2_created.uuid
    assert event_view3.person_involved[1].intermediate_value == "somevalue4"
    assert event_view3.person_involved[1].target[0].uuid == person3_created.uuid

    event_to_update = Event.EditSet(
        uuid=event_created.uuid,
        type="Event",
        label="An Event",
        person_involved=[
            {
                "uuid": event_view2.person_involved[0].uuid,
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue3",
                "target": [
                    {"type": "Person", "uuid": person2_created.uuid},
                    {"type": "Person", "uuid": person3_created.uuid},
                ],
            },
            {
                "type": "Intermediate[test_update_reified.<locals>.Person]",
                "intermediate_value": "somevalue4",
                "target": [{"type": "Person", "uuid": person3_created.uuid}],
            },
        ],
    )

    success = await event_to_update.update()

    event_view4 = await Event.get_view(uuid=event_created.uuid)
    assert event_view4.person_involved[0].intermediate_value == "somevalue3"
    assert event_view4.person_involved[0].target[0].uuid == person2_created.uuid
    assert event_view4.person_involved[0].target[1].uuid == person3_created.uuid


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_with_reified_chain(clear_database):
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
            RelationConfig(reverse_name="carried_out"),
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
                "type": "WithProxyActor[Identification[test_update_with_reified_chain.<locals>.Person]]",
                "target": [
                    {
                        "type": "Identification[test_update_with_reified_chain.<locals>.Person]",
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
                        "type": "Identification[test_update_with_reified_chain.<locals>.Person]",
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

    edit_event_from_db = await Event.get_edit_view(uuid=event_in_db.uuid)

    # Call update with no changes; should do nothing
    await edit_event_from_db.update()

    event_from_db = await Event.get_view(uuid=event_in_db.uuid)

    # And should not have a modified object
    assert not event_from_db.modified_by

    # Now, let's update a basic property

    # Re-get the data from the DB
    event_from_db = await Event.get_view(uuid=event_in_db.uuid)

    # Create a new WithProxyActor, swapping round Smith and Jones
    event_edit_set1 = Event.EditSet(
        uuid=event_from_db.uuid,
        type="Event",
        label="An Event Updated",
        carried_out_by=[
            {
                "label": "Smith acts as proxy for Jones",
                "type": "WithProxyActor[Identification[test_update_with_reified_chain.<locals>.Person]]",
                "target": [
                    {
                        "type": "Identification[test_update_with_reified_chain.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": person2_in_db.uuid,
                            }
                        ],
                    }
                ],
                "proxy": [
                    {
                        "type": "Identification[test_update_with_reified_chain.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": person1_in_db.uuid,
                            }
                        ],
                    }
                ],
            },
        ],
    )

    success = await event_edit_set1.update()

    assert success

    event_from_db2 = await Event.get_view(uuid=event_in_db.uuid)

    assert event_from_db2.label == "An Event Updated"

    assert event_from_db2.carried_out_by[0].head_type == "Event"

    assert event_from_db2.carried_out_by[0].label == "Smith acts as proxy for Jones"

    assert (
        event_from_db2.carried_out_by[0].target[0].target[0].uuid == person2_in_db.uuid
    )
    assert event_from_db2.carried_out_by[0].target[0].target[0].label == "TobyJones"
    assert (
        event_from_db2.carried_out_by[0].target[0].target[0].edge_properties.certainty
        == 1
    )

    assert (
        event_from_db2.carried_out_by[0].proxy[0].target[0].uuid == person1_in_db.uuid
    )

    event_edit_set2 = Event.EditSet(
        uuid=event_from_db2.uuid,
        type="Event",
        label="An Event Updated",
        carried_out_by=[
            {
                "uuid": event_from_db2.carried_out_by[0].uuid,
                "label": "Smith acts as proxy for Jones",
                "type": "WithProxyActor[Identification[test_update_with_reified_chain.<locals>.Person]]",
                "target": [
                    {
                        "uuid": event_from_db2.carried_out_by[0].target[0].uuid,
                        "type": "Identification[test_update_with_reified_chain.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 2},
                                "type": "Person",
                                "uuid": person2_in_db.uuid,
                            }
                        ],
                    }
                ],
                "proxy": [
                    {
                        "uuid": event_from_db2.carried_out_by[0].proxy[0].uuid,
                        "type": "Identification[test_update_with_reified_chain.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": person1_in_db.uuid,
                            }
                        ],
                    }
                ],
            },
        ],
    )

    success = await event_edit_set2.update()
    assert success

    event_from_db3 = await Event.get_view(uuid=event_in_db.uuid)

    assert event_from_db3

    assert (
        event_from_db3.carried_out_by[0].target[0].target[0].edge_properties.certainty
        == 2
    )


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_nested_edit_inline(clear_database):
    # TODO: this test needs to be made order-less (failing sometimes for no reason)

    class Factoid(BaseNode):
        statements: typing.Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_statement_in", create_inline=True, edit_inline=True
            ),
        ]

    class Statement(BaseNode):
        pass

    class Order(Statement):
        thing_ordered: typing.Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_ordered_in", create_inline=True, edit_inline=True
            ),
        ]

    class Activity(Statement):
        carried_out_by: typing.Annotated[
            Person, RelationConfig(reverse_name="carried_out")
        ]

    class Person(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    person1 = Person(type="Person", label="Person1")
    person1_created = await person1.create()

    factoid = Factoid(
        type="Factoid",
        label="A Factoid",
        statements=[
            {
                "type": "Order",
                "label": "An Activity Gets Ordered",
                "thing_ordered": [
                    {
                        "type": "Activity",
                        "label": "Person1 does a thing",
                        "carried_out_by": [
                            {
                                "type": "Person",
                                "uuid": person1_created.uuid,
                            }
                        ],
                    },
                ],
            }
        ],
    )

    factoid_created = await factoid.create()

    factoid_from_db = await Factoid.get_view(uuid=factoid_created.uuid)

    factoid_update1 = Factoid.EditSet(
        uuid=factoid_from_db.uuid,
        type="Factoid",
        label="A Factoid",
        statements=[
            {
                "uuid": factoid_from_db.statements[0].uuid,
                "type": "Order",
                "label": "An Order Gets Ordered",
                "thing_ordered": [
                    {
                        "type": "Order",
                        "label": "An activity gets ordered updated",
                        "thing_ordered": [
                            {
                                "type": "Activity",
                                "label": "Person1 does a thing updated",
                                "carried_out_by": [
                                    {
                                        "type": "Person",
                                        "uuid": person1_created.uuid,
                                    }
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    )

    success = await factoid_update1.update()
    assert success

    factoid_from_db1 = await Factoid.get_view(uuid=factoid_from_db.uuid)

    assert factoid_from_db1.modified_by == "DefaultUser"

    # Check top statement is still same statement
    assert factoid_from_db1.statements[0].uuid == factoid_from_db.statements[0].uuid

    assert factoid_from_db1.statements[0].label == "An Order Gets Ordered"

    assert factoid_from_db1.statements[0].thing_ordered[0].type == "Order"
    assert (
        factoid_from_db1.statements[0].thing_ordered[0].label
        == "An activity gets ordered updated"
    )

    assert (
        factoid_from_db1.statements[0].thing_ordered[0].thing_ordered[0].type
        == "Activity"
    )

    assert (
        factoid_from_db1.statements[0].thing_ordered[0].thing_ordered[0].label
        == "Person1 does a thing updated"
    )

    assert (
        factoid_from_db1.statements[0]
        .thing_ordered[0]
        .thing_ordered[0]
        .carried_out_by[0]
        .label
        == "Person1"
    )

    assert (
        factoid_from_db1.statements[0]
        .thing_ordered[0]
        .thing_ordered[0]
        .carried_out_by[0]
        .uuid
        == person1_created.uuid
    )

    # Create a new person
    person2 = Person(type="Person", label="Person2")
    person2_created = await person2.create()

    # Modify nothing but carried_out_by
    factoid_update2 = Factoid.EditSet(
        uuid=factoid_from_db.uuid,
        type="Factoid",
        label="A Factoid",
        statements=[
            {
                "uuid": factoid_from_db.statements[0].uuid,
                "type": "Order",
                "label": "An Order Gets Ordered",
                "thing_ordered": [
                    {
                        "uuid": factoid_from_db1.statements[0].thing_ordered[0].uuid,
                        "type": "Order",
                        "label": "An activity gets ordered updated",
                        "thing_ordered": [
                            {
                                "uuid": factoid_from_db1.statements[0]
                                .thing_ordered[0]
                                .thing_ordered[0]
                                .uuid,
                                "type": "Activity",
                                "label": "Person1 and Person2 do a thing updated",
                                "carried_out_by": [
                                    {
                                        "type": "Person",
                                        "uuid": person1_created.uuid,
                                    },
                                    {
                                        "type": "Person",
                                        "uuid": person2_created.uuid,
                                    },
                                ],
                            },
                        ],
                    }
                ],
            }
        ],
    )

    # Check we get back a modified_when after this datetime
    # from view returned below
    most_recent_modified_before = datetime.datetime.now(datetime.timezone.utc)

    success = await factoid_update2.update()

    factoid_from_db2 = await Factoid.get_view(uuid=factoid_from_db.uuid)

    assert factoid_from_db2.modified_when > most_recent_modified_before

    assert len(factoid_from_db2.statements) == 1

    assert (
        factoid_from_db2.statements[0]
        .thing_ordered[0]
        .thing_ordered[0]
        .carried_out_by[0]
        .uuid
        == person2_created.uuid
    )

    assert (
        factoid_from_db2.statements[0]
        .thing_ordered[0]
        .thing_ordered[0]
        .carried_out_by[1]
        .uuid
        == person1_created.uuid
    )

    assert (
        len(
            factoid_from_db2.statements[0]
            .thing_ordered[0]
            .thing_ordered[0]
            .carried_out_by
        )
        == 2
    )

    # Random thought to check whether UUID7 sortable
    assert person1_created.uuid < person2_created.uuid


@typing.no_type_check
@pytest.mark.asyncio
async def test_update_embedded():
    class Date(BaseNode):
        precise_date: datetime.date
        is_day_of_saint: typing.Annotated[
            Saint, RelationConfig(reverse_name="is_saints_day")
        ]

    class Event(BaseNode):
        when: typing.Annotated[Embedded[Date], annotated_types.MaxLen(2)]

    class Saint(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    st_george = Saint(type="Saint", label="St George")
    st_george_created = await st_george.create()

    st_patrick = Saint(type="Saint", label="St Patrick")
    st_patrick_created = await st_patrick.create()

    st_david = Saint(type="Saint", label="St David")
    st_david_created = await st_david.create()

    event = Event(
        type="Event",
        label="An Event",
        when=[
            {
                "type": "Date",
                "precise_date": datetime.date.today(),
                "is_day_of_saint": [{"type": "Saint", "uuid": st_george_created.uuid}],
            }
        ],
    )

    event_in_db = await event.create()
    assert event_in_db

    event_from_db = await Event.get_view(uuid=event_in_db.uuid)
    assert event_from_db
    assert event_from_db.when[0].uuid
    assert event_from_db.when[0].precise_date == datetime.date.today()
    assert event_from_db.when[0].is_day_of_saint[0].uuid == st_george_created.uuid

    # First update references existing Embedded Node
    event_update = Event.EditSet(
        uuid=event_from_db.uuid,
        type="Event",
        label="An Event",
        when=[
            {
                "uuid": event_from_db.when[0].uuid,
                "type": "Date",
                "precise_date": datetime.date.today() + datetime.timedelta(days=1),
                "is_day_of_saint": [{"type": "Saint", "uuid": st_patrick_created.uuid}],
            }
        ],
    )

    success = await event_update.update()
    assert success

    event_from_db2 = await Event.get_view(uuid=event_in_db.uuid)
    assert len(event_from_db2.when) == 1

    assert event_from_db2.when[
        0
    ].precise_date == datetime.date.today() + datetime.timedelta(days=1)
    assert event_from_db2.when[0].is_day_of_saint[0].uuid == st_patrick_created.uuid

    # Second update creates new Embedded node replacing the old one
    event_update = Event.EditSet(
        uuid=event_from_db.uuid,
        type="Event",
        label="An Event",
        when=[
            {
                # "uuid": event_from_db.when[0].uuid,
                "type": "Date",
                "precise_date": datetime.date.today() + datetime.timedelta(days=1),
                "is_day_of_saint": [{"type": "Saint", "uuid": st_david_created.uuid}],
            }
        ],
    )
    success = await event_update.update()
    assert success

    event_from_db3 = await Event.get_view(uuid=event_in_db.uuid)
    assert len(event_from_db2.when) == 1

    assert event_from_db3.when[
        0
    ].precise_date == datetime.date.today() + datetime.timedelta(days=1)
    assert event_from_db3.when[0].is_day_of_saint[0].uuid == st_david_created.uuid


@typing.no_type_check
@pytest.mark.asyncio
async def test_speed():
    return

    class Event(BaseNode):
        event_type: str
        persons_involved: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    class Person(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    persons = [Person(type="Person", label=f"Person{n}") for n in range(100)]
    persons_created = []
    for person in persons:
        person_created = await person.create()
        persons_created.append(person_created)

    event = Event(
        type="Event",
        label="An Event",
        event_type="Some type of event",
        persons_involved=[
            {"type": "Person", "uuid": p.uuid} for p in persons_created[10:50]
        ],
    )
    created_event = await event.create()

    event_to_update = Event.EditSet(
        uuid=created_event.uuid,
        type="Event",
        label="An Event Updated",
        event_type="Some updated type of event",
        persons_involved=[{"type": "Person", "uuid": p.uuid} for p in persons_created][
            30:80
        ],
    )

    await event_to_update.update()
