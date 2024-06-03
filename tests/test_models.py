from __future__ import annotations

import pytest

import typing
import uuid

import annotated_types
import pydantic

from pangloss.model_config.model_manager import ModelManager
from pangloss.models import BaseNode, RelationConfig


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
