from typing import Annotated

import pytest
import pytest_asyncio

from pangloss import initialise_models
from pangloss.models import BaseNode, ReifiedRelation, RelationConfig
from pangloss.neo4j.database import DatabaseUtils


@pytest_asyncio.fixture
async def reset_db():
    await DatabaseUtils.dangerously_clear_database()
    yield


@pytest.mark.asyncio
async def test_save_method_works_on_create_model():
    class Thing(BaseNode):
        name: str

    initialise_models()

    await Thing(
        id="http://something.com/thing", label="Thing", type="Thing", name="A Thing"
    ).save()

    await Thing(
        id="http://something.com/thing",
        label="Other Thing",
        type="Thing",
        name="A Thing",
    ).save()


@pytest.mark.asyncio
async def test_create_with_relation():
    class Person(BaseNode):
        pass

    class Thing(BaseNode):
        is_person_of_thing: Annotated[
            Person,
            RelationConfig(reverse_name="is_thing_of_person", create_inline=True),
        ]

    class SubThing(Thing):
        is_person_of_subthing: Annotated[
            Person,
            RelationConfig(
                reverse_name="is_subthing_of_person",
                subclasses_relation=["is_person_of_thing"],
            ),
        ]

    class SubSubThing(SubThing):
        is_person_of_subsubthing: Annotated[
            Person,
            RelationConfig(
                reverse_name="is_person_of_subsubthing",
                subclasses_relation=["is_person_of_subthing"],
            ),
        ]

    initialise_models()

    person = await Person(label="John Smith").save()

    await SubSubThing(
        label="Thing",
        type="SubSubThing",
        name="A Thing",
        is_person_of_subsubthing=[{"type": "Person", "id": person.id}],
    ).save()


@pytest.mark.asyncio
async def test_creation_with_reified_relations():
    class IntermediateA[T](ReifiedRelation[T]):
        pass

    class IntermediateB[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Thing(BaseNode):
        is_person_of_thing: Annotated[
            IntermediateA[IntermediateB[Person]] | IntermediateA[Person],
            RelationConfig(reverse_name="is_thing_of_person", create_inline=True),
        ]

    initialise_models()

    person = await Person(label="John Smith").save()

    thing = Thing(
        type="Thing",
        label="A Thing",
        is_person_of_thing=[
            {
                "type": "IntermediateA",
                "target": [
                    {
                        "type": "IntermediateB",
                        "target": [{"type": "Person", "id": person.id}],
                    }
                ],
            }
        ],
    )

    await thing.save()

    thing2 = Thing(
        type="Thing",
        label="A Thing",
        is_person_of_thing=[
            {
                "type": "IntermediateA",
                "target": [{"type": "Person", "id": person.id}],
            }
        ],
    )

    await thing2.save()
