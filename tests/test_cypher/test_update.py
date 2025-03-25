from typing import Annotated, no_type_check

import pytest

from pangloss import initialise_models
from pangloss.model_config.models_base import ReifiedRelation
from pangloss.models import BaseNode, RelationConfig


@no_type_check
@pytest.mark.asyncio
async def test_basic_update():
    class Person(BaseNode):
        name: str

    initialise_models()

    person = await Person(label="John Smith", name="John Smith").create_and_get()

    person.name = "John (The Updated) Smith"

    await person.update()

    person_from_db = await Person.get_view(id=person.id)
    assert person_from_db.name == "John (The Updated) Smith"


@no_type_check
@pytest.mark.asyncio
async def test_update_direct_relation():
    class Cat(BaseNode):
        pass

    class Person(BaseNode):
        has_cat: Annotated[Cat, RelationConfig(reverse_name="is_cat_of")]

    initialise_models()

    cat1 = await Cat(label="Mister Fluffy").create()
    cat2 = await Cat(label="Mister Cuddly").create()

    person = await Person(
        label="John Smith", has_cat=[{"type": "Cat", "id": cat1.id}]
    ).create_and_get()

    person.has_cat = [{"type": "Cat", "id": cat2.id}]

    await person.update()


@no_type_check
@pytest.mark.asyncio
async def test_update_reified_relation():
    class IntermediateOne[T](ReifiedRelation[T]):
        pass

    class IntermediateTwo[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        involves_person: Annotated[
            IntermediateOne[IntermediateTwo[Person]],
            RelationConfig(reverse_name="is_involved_in_event"),
        ]

    initialise_models()

    person = await Person(label="John Smith").create()
    event = await Event(
        label="Party",
        involves_person=[
            {
                "type": "IntermediateOne",
                "target": [
                    {
                        "type": "IntermediateTwo",
                        "target": [{"type": "Person", "id": person.id}],
                    }
                ],
            }
        ],
    ).create_and_get()

    other_person = await Person(label="Jane Doe").create()

    event_update = Event.EditHeadSet(
        label="Party (Updated)",
        id=event.id,
        involves_person=[
            {
                "type": "IntermediateOne",
                # "id": event.involves_person[0].id,
                "target": [
                    {
                        "type": "IntermediateTwo",
                        "target": [{"type": "Person", "id": other_person.id}],
                    }
                ],
            }
        ],
    )

    await event_update.update()

    event_from_db = await Event.get_edit_view(id=event.id)
    assert event_from_db

    assert event_from_db.label == "Party (Updated)"
    assert event_from_db.id == event.id
    # Should have a new id for event.involves_person[0]
    assert event_from_db.involves_person[0].id != event.involves_person[0].id

    # Now update IntermediateOne, keeping the same id
    event_update2 = Event.EditHeadSet(
        label="Party (Updated)",
        id=event.id,
        involves_person=[
            {
                "type": "IntermediateOne",
                "id": event_from_db.involves_person[0].id,
                "target": [
                    {
                        "type": "IntermediateTwo",
                        "target": [
                            {"type": "Person", "id": other_person.id},
                            {"type": "Person", "id": person.id},
                        ],
                    },
                ],
            }
        ],
    )

    await event_update2.update()
    event_from_db2 = await Event.get_edit_view(id=event.id)
    assert event_from_db2
    assert event_from_db2.involves_person[0].id == event_from_db.involves_person[0].id

    assert set(t.id for t in event_from_db2.involves_person[0].target[0].target) == set(
        [other_person.id, person.id]
    )


@no_type_check
@pytest.mark.asyncio
async def test_update_create_inline():
    class Person(BaseNode):
        pass

    class Task(BaseNode):
        carried_out_by_person: Annotated[
            Person, RelationConfig(reverse_name="carries_out_task")
        ]

    class Order(BaseNode):
        person_giving_order: Annotated[
            Person, RelationConfig(reverse_name="gives_order")
        ]
        task_ordered: Annotated[
            Task,
            RelationConfig(
                reverse_name="is_ordered", create_inline=True, edit_inline=True
            ),
        ]

    class Factoid(BaseNode):
        has_statements: Annotated[
            Order,
            RelationConfig(
                reverse_name="is_statement_of",
                create_inline=True,
                edit_inline=True,
            ),
        ]

    initialise_models()

    person_giving_order = await Person(label="Kaiser Maximilian").create()
    other_person_giving_order = await Person(label="Kaiser Wilhelm").create()
    person_carrying_out_task = await Person(label="John Smith").create()

    factoid = await Factoid(
        label="Maximilian orders John Smith to complete a task",
        has_statements=[
            {
                "label": "Order 1",
                "type": "Order",
                "person_giving_order": [
                    {"type": "Person", "id": person_giving_order.id}
                ],
                "task_ordered": [
                    {
                        "label": "Task 1",
                        "carried_out_by_person": [
                            {"type": "Person", "id": person_carrying_out_task.id}
                        ],
                    }
                ],
            }
        ],
    ).create_and_get()

    factoid_edit = Factoid.EditHeadSet(
        id=factoid.id,
        label="Wilhelm orders John Smith to complete a task (Updated)",
        has_statements=[
            {
                "id": factoid.has_statements[0].id,
                "label": "Order 1 (Updated)",
                "type": "Order",
                "person_giving_order": [
                    {"type": "Person", "id": other_person_giving_order.id}
                ],
                "task_ordered": [
                    {
                        "label": "Task 2",
                        "carried_out_by_person": [
                            {"type": "Person", "id": person_carrying_out_task.id}
                        ],
                    }
                ],
            }
        ],
    )
    await factoid_edit.update()

    factoid_edit_updated = await Factoid.get_edit_view(id=factoid.id)
    assert (
        factoid_edit_updated.label
        == "Wilhelm orders John Smith to complete a task (Updated)"
    )
    assert factoid_edit_updated.has_statements[0].id == factoid.has_statements[0].id
    assert (
        factoid_edit_updated.has_statements[0].person_giving_order[0].id
        == other_person_giving_order.id
    )
    assert factoid_edit_updated.has_statements[0].label == "Order 1 (Updated)"
    assert factoid_edit_updated.has_statements[0].task_ordered[0].label == "Task 2"
