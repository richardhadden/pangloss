from __future__ import annotations

import typing

import pytest
import pytest_asyncio

from pangloss.database import Database
from pangloss.model_config.model_manager import ModelManager
from pangloss.models import (
    BaseNode,
    EdgeModel,
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
async def test_get_reverse_relation_via_reified_chain_with_subtype(clear_database):
    class Person(BaseNode):
        pass

    class Dude(Person):
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
        thrown_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="threw"),
        ]

    class Party(Event):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    person1 = Person(type="Person", label="JohnSmith")
    person1_in_db = await person1.create()

    dude1 = Dude(type="Dude", label="TobyJones")
    dude1_in_db = await dude1.create()

    party = Party(
        type="Party",
        label="A Party",
        thrown_by=[
            {
                "label": "Jones acts as proxy for Smith",
                "type": "WithProxyActor[Identification[test_get_reverse_relation_via_reified_chain_with_subtype.<locals>.Person]]",
                "target": [
                    {
                        "type": "Identification[test_get_reverse_relation_via_reified_chain_with_subtype.<locals>.Person]",
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
                        "type": "Identification[test_get_reverse_relation_via_reified_chain_with_subtype.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Dude",
                                "uuid": dude1_in_db.uuid,
                            }
                        ],
                    }
                ],
            },
        ],
    )

    party_in_db = await party.create()

    person_view = await Person.get_view(uuid=person1_in_db.uuid)

    assert person_view.threw[0].type == "Party"

    assert (
        person_view.threw[0].thrown_by[0].type
        == "WithProxyActor[Identification[test_get_reverse_relation_via_reified_chain_with_subtype.<locals>.Person]]"
    )


@typing.no_type_check
@pytest.mark.asyncio
async def test_cypher_get_list():
    class Person(BaseNode):
        pass

    class Dude(Person):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    persons = []
    for i in range(20):
        person = Person(type="Person", label=f"Person {i}")
        person_in_db = await person.create()
        persons.append(person_in_db)

    dudes = []
    for i in range(5):
        dude = Dude(type="Dude", label=f"Dude {i}")
        dude_in_db = await dude.create()
        dudes.append(dude_in_db)

    persons_from_db = await Person.get_list(page_size=10)
    assert persons_from_db["count"] == 25
    assert persons_from_db["page"] == 1
    assert persons_from_db["totalPages"] == 3

    assert set(persons_from_db["results"]) == set([*dudes[-5:], *persons[-5:]])
