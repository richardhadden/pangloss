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
async def test_get_reverse_relation_via_reified_chain_with_subtype():
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
        thrown_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="carried_out"),
        ]

    class Party(Event):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    print(Party.ReferenceView)

    person1 = Person(type="Person", label="JohnSmith")
    person1_in_db = await person1.create()

    person2 = Person(type="Person", label="TobyJones")
    person2_in_db = await person2.create()

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
                                "type": "Person",
                                "uuid": person2_in_db.uuid,
                            }
                        ],
                    }
                ],
            },
        ],
    )

    party_in_db = await party.create()
