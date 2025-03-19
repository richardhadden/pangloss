import datetime
from typing import Annotated, no_type_check

import pytest
import pytest_asyncio
from pydantic import AnyHttpUrl
from ulid import ULID

from pangloss import initialise_models
from pangloss.model_config.models_base import (
    BaseMeta,
    BoundField,
    EdgeModel,
    ReifiedRelationNode,
)
from pangloss.models import BaseNode, Embedded, ReifiedRelation, RelationConfig
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


@no_type_check
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

    person = await Person(label="John Smith").create_and_get()

    thing = await Thing(
        type="Thing",
        label="A Thing",
        uris=["http://things.com/1"],
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
    ).create_and_get()

    assert isinstance(thing, Thing.EditHeadView)
    assert thing.label == "A Thing"
    assert thing.is_person_of_thing[0].type == "IntermediateA"
    assert thing.is_person_of_thing[0].target[0].type == "IntermediateB"
    assert thing.is_person_of_thing[0].target[0].target[0].type == "Person"
    assert thing.is_person_of_thing[0].target[0].target[0].id == person.id

    thing2 = await Thing(
        type="Thing",
        label="A Thing",
        is_person_of_thing=[
            {
                "type": "IntermediateA",
                "target": [{"type": "Person", "id": person.id}],
            }
        ],
    ).create()

    assert isinstance(thing2, Thing.ReferenceView)
    assert thing2.type == "Thing"
    assert isinstance(thing2.id, ULID)

    thing_view = await Thing.get_view(id=thing.id)

    assert thing_view.created_when < datetime.datetime.now(datetime.timezone.utc)
    assert thing_view.created_by == "DefaultUser"

    assert set(thing_view.uris) == set(
        [
            AnyHttpUrl(f"http://pangloss_test.com/Thing/{thing.id}"),
            AnyHttpUrl("http://things.com/1"),
        ]
    )


@no_type_check
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

    person_id = gen_ulid()
    thing = await Thing(
        type="Thing",
        label="A Thing",
        is_person_of_thing=[{"type": "Person", "id": person_id, "label": "A Person"}],
    ).create_and_get()

    assert thing.label == "A Thing"
    assert isinstance(thing.is_person_of_thing[0], Person.ReferenceView)
    assert thing.is_person_of_thing[0].id == person_id
    assert thing.is_person_of_thing[0].label == "A Person"

    person = await Person.get_view(id=person_id)

    assert isinstance(person.is_thing_of_person[0], Thing.ReferenceView)
    assert person.is_thing_of_person[0].id == thing.id
    assert person.is_thing_of_person[0].label == "A Thing"


@no_type_check
@pytest.mark.asyncio
async def test_write_complex_object():
    class Certainty(EdgeModel):
        certainty: float

    class Identification[T](ReifiedRelation[T]):
        target: Annotated[
            T, RelationConfig(reverse_name="is_target_of", edge_model=Certainty)
        ]

    class WithProxy[T](ReifiedRelationNode[T]):
        proxy: Annotated[
            T,
            RelationConfig(reverse_name="acts_as_proxy_in"),
        ]

    class Reference(BaseNode):
        pass

    class Citation(BaseNode):
        source: Annotated[
            Reference,
            RelationConfig(reverse_name="is_source_of"),
        ]
        page: int

    class Entity(BaseNode):
        class Meta(BaseMeta):
            abstract = True
            create_by_reference = True

    class Person(Entity):
        pass

    class Object(Entity):
        pass

    class Statement(BaseNode):
        class Meta(BaseMeta):
            abstract = True

    class CreationOfObject(Statement):
        person_creating_object: Annotated[
            WithProxy[Identification[Person]],
            RelationConfig(reverse_name="creator_in_object_creation"),
        ]
        object_created: Annotated[Object, RelationConfig(reverse_name="was_created_in")]

    class Order(Statement):
        person_giving_order: Annotated[
            WithProxy[Identification[Person]],
            RelationConfig(reverse_name="gave_order"),
        ]
        person_receiving_order: Annotated[
            Identification[Person],
            RelationConfig(
                reverse_name="received_order",
            ),
        ]
        thing_ordered: Annotated[
            CreationOfObject,
            RelationConfig(
                reverse_name="was_ordered_in",
                create_inline=True,
                edit_inline=True,
                bind_fields_to_related=[
                    BoundField(
                        parent_field_name="person_receiving_order",
                        bound_field_name="person_creating_object",
                    )
                ],
            ),
        ]

    class Factoid(BaseNode):
        Embedded[Citation]
        has_statements: Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_statement_in", create_inline=True, edit_inline=True
            ),
        ]

    initialise_models()
