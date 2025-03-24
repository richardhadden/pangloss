import asyncio
import datetime
from typing import Annotated, no_type_check

import pytest
import pytest_asyncio
from pydantic import AnyHttpUrl
from ulid import ULID

from pangloss import initialise_models
from pangloss.indexes import (
    _clear_full_text_indexes,
    _install_index_and_constraints_from_text,
)
from pangloss.model_config.models_base import (
    BaseMeta,
    EdgeModel,
    HeritableTrait,
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

    assert isinstance(thing, Thing.EditHeadSet)
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
        is_person_of_thing=[
            {"type": "Person", "id": person_id, "label": "A Person", "create": True}
        ],
    ).create_and_get()

    assert isinstance(thing, Thing.EditHeadSet)
    assert thing.label == "A Thing"
    assert isinstance(thing.is_person_of_thing[0], Person.ReferenceSet)
    assert thing.is_person_of_thing[0].id == person_id

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

    class ReferenceableType(HeritableTrait):
        pass

    class Citation(BaseNode):
        reference: Annotated[
            ReferenceableType,
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

    class Book(Object, ReferenceableType):
        pass

    class Statement(BaseNode):
        class Meta(BaseMeta):
            abstract = True

    class CreationOfObject(Statement):
        person_creating_object: Annotated[
            Identification[Person],
            RelationConfig(reverse_name="creator_in_object_creation"),
        ]
        object_created: Annotated[Object, RelationConfig(reverse_name="was_created_in")]

    class Order(Statement):
        person_giving_order: Annotated[
            WithProxy[Identification[Person]] | Identification[Person],
            RelationConfig(
                reverse_name="gave_order", default_reified_type="Identification"
            ),
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
            ),
        ]

    class Factoid(BaseNode):
        citation: Embedded[Citation]
        has_statements: Annotated[
            Statement,
            RelationConfig(
                reverse_name="is_statement_in", create_inline=True, edit_inline=True
            ),
        ]

    initialise_models()
    await _install_index_and_constraints_from_text()

    book = await Book(label="On The Origins of the Thing").create()

    assert book

    john_smith = await Person(label="John Smith").create()

    kaiser_maximilian = await Person(label="Kaiser Maximilian").create()

    secretary = await Person(label="KM's Secretary").create()

    an_object = await Object(label="An Object").create()

    factoid = Factoid(
        type="Factoid",
        label="Kaiser Maximilian, through his secretary, orders John Smith to create an Object",
        citation=[
            dict(
                type="Citation",
                reference=[
                    dict(type="Book", id=book.id),
                ],
                page=1,
            )
        ],
        has_statements=[
            dict(
                type="Order",
                label="Kaiser Maximilian, through his secretary, orders John Smith to create an Object",
                person_giving_order=[
                    dict(
                        type="WithProxy",
                        label="Maximilian's Secretary acts as proxy for Maximilian",
                        target=[
                            dict(
                                type="Identification",
                                target=[
                                    dict(
                                        type="Person",
                                        id=kaiser_maximilian.id,
                                        edge_properties=dict(certainty=1.0),
                                    )
                                ],
                            ),
                        ],
                        proxy=[
                            dict(
                                type="Identification",
                                target=[
                                    dict(
                                        type="Person",
                                        id=secretary.id,
                                        edge_properties=dict(certainty=1.0),
                                    )
                                ],
                            ),
                        ],
                    )
                ],
                person_receiving_order=[
                    dict(
                        type="Identification",
                        target=[
                            dict(
                                type="Person",
                                id=john_smith.id,
                                edge_properties=dict(certainty=1.0),
                            )
                        ],
                    ),
                ],
                thing_ordered=[
                    dict(
                        type="CreationOfObject",
                        label="John Smith creates an Object",
                        object_created=[
                            dict(type="Object", id=an_object.id),
                        ],
                        person_creating_object=[
                            dict(
                                type="Identification",
                                target=[
                                    dict(
                                        type="Person",
                                        id=john_smith.id,
                                        edge_properties=dict(certainty=1.0),
                                    )
                                ],
                            )
                        ],
                    )
                ],
            )
        ],
    )

    factoid = await factoid.create_and_get()

    factoid_view = await Factoid.get_view(id=factoid.id)

    assert factoid_view.citation[0].type == "Citation"
    assert factoid_view.citation[0].id
    assert factoid_view.citation[0].reference
    assert factoid_view.citation[0].reference[0].type == "Book"
    assert factoid_view.citation[0].reference[0].id == book.id
    assert factoid_view.citation[0].reference[0].label == "On The Origins of the Thing"

    assert factoid_view.has_statements
    assert factoid_view.has_statements[0].type == "Order"
    assert factoid_view.has_statements[0].person_giving_order
    assert factoid_view.has_statements[0].person_giving_order[0].type == "WithProxy"
    assert (
        factoid_view.has_statements[0].person_giving_order[0].label
        == "Maximilian's Secretary acts as proxy for Maximilian"
    )
    assert factoid.has_statements[0].person_giving_order[0].target
    assert (
        factoid.has_statements[0].person_giving_order[0].target[0].type
        == "Identification"
    )
    assert factoid.has_statements[0].person_giving_order[0].target[0].target
    assert (
        factoid.has_statements[0].person_giving_order[0].target[0].target[0].type
        == "Person"
    )
    assert (
        factoid.has_statements[0].person_giving_order[0].target[0].target[0].label
        == "Kaiser Maximilian"
    )
    assert (
        factoid.has_statements[0].person_giving_order[0].target[0].target[0].id
        == kaiser_maximilian.id
    )
    assert (
        factoid.has_statements[0]
        .person_giving_order[0]
        .target[0]
        .target[0]
        .edge_properties.certainty
        == 1
    )

    assert (
        factoid.has_statements[0].person_giving_order[0].proxy[0].type
        == "Identification"
    )
    assert factoid.has_statements[0].person_giving_order[0].proxy[0].target
    assert (
        factoid.has_statements[0].person_giving_order[0].proxy[0].target[0].type
        == "Person"
    )
    assert (
        factoid.has_statements[0].person_giving_order[0].proxy[0].target[0].label
        == "KM's Secretary"
    )

    assert (
        factoid.has_statements[0].person_giving_order[0].proxy[0].target[0].id
        == secretary.id
    )
    assert (
        factoid.has_statements[0]
        .person_giving_order[0]
        .proxy[0]
        .target[0]
        .edge_properties.certainty
        == 1
    )

    assert factoid.has_statements[0].thing_ordered
    assert factoid.has_statements[0].thing_ordered[0].type == "CreationOfObject"
    assert factoid.has_statements[0].thing_ordered[0].id
    assert factoid.has_statements[0].thing_ordered[0].object_created
    assert factoid.has_statements[0].thing_ordered[0].object_created[0].type == "Object"
    assert (
        factoid.has_statements[0].thing_ordered[0].object_created[0].id == an_object.id
    )
    assert (
        factoid.has_statements[0].thing_ordered[0].object_created[0].label
        == "An Object"
    )
    assert factoid.has_statements[0].thing_ordered[0].person_creating_object
    assert (
        factoid.has_statements[0].thing_ordered[0].person_creating_object[0].type
        == "Identification"
    )
    assert factoid.has_statements[0].thing_ordered[0].person_creating_object[0].target
    assert (
        factoid.has_statements[0]
        .thing_ordered[0]
        .person_creating_object[0]
        .target[0]
        .type
        == "Person"
    )
    assert (
        factoid.has_statements[0]
        .thing_ordered[0]
        .person_creating_object[0]
        .target[0]
        .id
        == john_smith.id
    )
    assert (
        factoid.has_statements[0]
        .thing_ordered[0]
        .person_creating_object[0]
        .target[0]
        .label
        == "John Smith"
    )
    assert (
        factoid.has_statements[0]
        .thing_ordered[0]
        .person_creating_object[0]
        .target[0]
        .edge_properties.certainty
        == 1
    )

    toby_jones = await Object(label="Toby Jones").create()

    await asyncio.sleep(1)

    search_results = await Factoid.get_list()
    assert len(search_results.results) == 1

    # Persons should have "M" in the name, i.e. all below but not toby_jones
    search_results = await Person.get_list(q="M")
    assert len(search_results.results) == 3
    assert set([r.label for r in search_results.results]) == set(
        ["John Smith", "KM's Secretary", "Kaiser Maximilian"]
    )

    # Should get the book name from being associated with this factoid
    search_results = await Factoid.get_list(q="origins", deep_search=True)
    assert search_results.results
    assert search_results.results[0].id == factoid.id

    await _clear_full_text_indexes()


@no_type_check
@pytest.mark.asyncio
async def test_list_with_multiple_types():
    class Text(BaseNode):
        pass

    class Book(Text):
        pass

    class NiceBook(Book):
        pass

    class Magazine(Text):
        pass

    initialise_models()

    await _install_index_and_constraints_from_text()

    book = await Book(label="A Book").create()
    magazine = await Magazine(label="A Magazine").create()

    search_results = await Text.get_list()
    assert len(search_results) == 2

    assert set(search_results.results) == set([book, magazine])


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

    person.has_cat = [Cat.ReferenceSet(**{"type": "Cat", "id": cat2.id})]

    person.model_dump(mode="json")
    # await person.update()
