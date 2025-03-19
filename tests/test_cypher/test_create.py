from typing import Annotated, no_type_check

import pytest
import pytest_asyncio
from pydantic import AnyHttpUrl
from ulid import ULID

from pangloss import initialise_models
from pangloss.model_config.models_base import BaseMeta
from pangloss.models import BaseNode, ReifiedRelation, RelationConfig
from pangloss.neo4j.database import DatabaseUtils
from pangloss.utils import gen_ulid


@pytest_asyncio.fixture
async def reset_db():
    await DatabaseUtils.dangerously_clear_database()
    yield


@no_type_check
@pytest.mark.asyncio
async def test_save_method_works_on_create_model():
    class Thing(BaseNode):
        name: str

    initialise_models()

    thing = await Thing(
        id="http://something.com/thing", label="Thing", type="Thing", name="A Thing"
    ).create_and_get()

    assert isinstance(thing.id, ULID)
    assert set(thing.uris) == set(
        [
            AnyHttpUrl(f"http://pangloss_test.com/Thing/{thing.id}"),
            AnyHttpUrl("http://something.com/thing"),
        ]
    )

    assert thing.label == "Thing"
    assert thing.type == "Thing"
    assert thing.name == "A Thing"


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

    person = await Person(label="John Smith").create()

    await SubSubThing(
        label="Thing",
        type="SubSubThing",
        name="A Thing",
        is_person_of_subsubthing=[{"type": "Person", "id": person.id}],
    ).create()


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
            RelationConfig(reverse_name="is_thing_of_person"),
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


@pytest.mark.asyncio
async def test_reference_create():
    class Person(BaseNode):
        class Meta(BaseMeta):
            create_by_reference = True

    class Thing(BaseNode):
        is_person_of_thing: Annotated[
            Person,
            RelationConfig(reverse_name="is_thing_of_person"),
        ]

    initialise_models()

    print(Thing.Create.model_fields["is_person_of_thing"])

    thing = await Thing(
        type="Thing",
        label="A Thing",
        is_person_of_thing=[{"type": "Person", "id": gen_ulid(), "label": "A Person"}],
    ).save()
