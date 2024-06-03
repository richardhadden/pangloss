from __future__ import annotations

import pytest

import typing
import uuid

import annotated_types
import pydantic

from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.models_base import Embedded
from pangloss.models import (
    BaseNode,
    RelationConfig,
    RelationPropertiesModel,
    ReifiedRelation,
    HeritableTrait,
)


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


@typing.no_type_check
def test_create_with_base_model():
    class RelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        name: str
        age: int
        list_of_things: list[str]
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="has_reverse_relation_to_thing",
                validators=[annotated_types.MaxLen(1)],
            ),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    related_thing_reference_one = RelatedThing.ReferenceSet(uuid=uuid.uuid4())
    related_thing_reference_two = RelatedThing.ReferenceSet(uuid=uuid.uuid4())

    thing = Thing(
        label="A Thing",
        name="A Thing Name",
        age=100,
        list_of_things=["one", "two", "three"],
        related_to=[related_thing_reference_one._as_dict()],
    )

    assert thing.label == "A Thing"
    assert thing.name == "A Thing Name"
    assert thing.age == 100
    assert thing.list_of_things == ["one", "two", "three"]

    with pytest.raises(pydantic.ValidationError):
        Thing(
            label="A Thing",
            name="A Thing Name",
            age=100,
            list_of_things=["one", "two", "three"],
            related_to=[
                related_thing_reference_one._as_dict(),
                related_thing_reference_two._as_dict(),
            ],
        )


@typing.no_type_check
def test_create_with_inline_create():
    class RelatedThing(BaseNode):
        number: int

    class Thing(BaseNode):
        name: str
        age: int
        list_of_things: list[str]
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="has_reverse_relation_to_thing",
                validators=[annotated_types.MaxLen(1)],
                create_inline=True,
            ),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    thing = Thing(
        label="A Thing",
        name="A Thing Name",
        age=100,
        list_of_things=["one", "two", "three"],
        related_to=[
            {"type": "RelatedThing", "label": "A Related Thing", "number": 100}
        ],
    )

    assert thing.related_to[0] == RelatedThing(label="A Related Thing", number=100)


@typing.no_type_check
def test_create_with_embedded_node():
    class EmbeddedThing(BaseNode):
        number: int

    class Thing(BaseNode):
        name: str
        age: int
        list_of_things: list[str]
        embedded_thing: Embedded[EmbeddedThing]

    ModelManager.initialise_models(_defined_in_test=True)

    Thing(
        label="A Thing",
        name="A Thing Name",
        age=100,
        list_of_things=["one", "two", "three"],
        embedded_thing=[{"type": "EmbeddedThing", "number": 1}],
    )


@typing.no_type_check
def test_create_with_relation_property_model():
    class ThingRelatedThingRelation(RelationPropertiesModel):
        certainty: int

    class RelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="has_relation_to", relation_model=ThingRelatedThingRelation
            ),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Thing(
        label="A Thing",
        related_to=[
            {
                "type": "RelatedThing",
                "uuid": uuid.uuid4(),
                "relation_properties": {"certainty": 1},
            }
        ],
    )


@typing.no_type_check
def test_create_with_reified_relation():
    class IdentificationCertainty(RelationPropertiesModel):
        certainty: int

    class ThingToIdentifcation(RelationPropertiesModel):
        something: str

    T = typing.TypeVar("T")

    class Identification(ReifiedRelation[T]):
        target: typing.Annotated[
            T,
            RelationConfig(
                "is_target_of_identification",
                relation_model=IdentificationCertainty,
                validators=[annotated_types.MinLen(1)],
            ),
        ]
        identification_description: str

    class RelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        related_to: typing.Annotated[
            Identification[RelatedThing],
            RelationConfig(
                reverse_name="is_related_to", relation_model=ThingToIdentifcation
            ),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    thing = Thing(
        label="A Thing",
        related_to=[
            {
                "type": "Identification[test_create_with_reified_relation.<locals>.RelatedThing]",
                "target": [
                    {
                        "type": "RelatedThing",
                        "uuid": uuid.uuid4(),
                        "relation_properties": {"certainty": 1},
                    }
                ],
                "identification_description": "not bad",
                "relation_properties": {"something": "some thing"},
            }
        ],
    )

    assert thing.related_to[0].target[0].type == "RelatedThing"
    assert thing.related_to[0].target[0].relation_properties.certainty == 1


@typing.no_type_check
def test_initialise_relation_with_trait():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            Relatable, RelationConfig(reverse_name="has_relation_to")
        ]

    class Relatable(HeritableTrait):
        something: str

    class OtherThing(BaseNode, Relatable):
        pass

    class OtherOtherThing(BaseNode, Relatable):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    other_thing_uuid = uuid.uuid4()
    other_thing = OtherThing.ReferenceSet(uuid=other_thing_uuid)
    other_other_thing_uuid = uuid.uuid4()
    other_other_thing = OtherOtherThing.ReferenceSet(uuid=other_other_thing_uuid)

    thing = Thing(
        label="A Thing",
        related_to=[other_thing._as_dict(), other_other_thing._as_dict()],
    )

    assert thing.related_to[0].type == "OtherThing"
    assert thing.related_to[0] == OtherThing.ReferenceSet(uuid=other_thing_uuid)
    assert thing.related_to[1].type == "OtherOtherThing"
    assert thing.related_to[1] == OtherOtherThing.ReferenceSet(
        uuid=other_other_thing_uuid
    )
