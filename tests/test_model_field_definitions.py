from __future__ import annotations

import enum
import typing

import annotated_types
import pytest

from pangloss.exceptions import PanglossConfigError
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.field_definitions import (
    LiteralFieldDefinition,
    ListFieldDefinition,
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.models_base import NonHeritableTrait
from pangloss.models import (
    BaseNode,
    Embedded,
    RelationConfig,
    ReifiedRelation,
    HeritableTrait,
)


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


def test_model_registers_itself_with_model_manager():
    class Thing(BaseNode):
        pass

    assert ModelManager.registered_models == [Thing]


def test_model_adds_type_on_creation():
    class Thing(BaseNode):
        pass

    assert Thing.model_fields["type"].annotation == typing.Literal["Thing"]


"""
def test_model_field_definition_fails_with_not_allowed_type():
    with pytest.raises(pydantic.errors.PydanticSchemaGenerationError):

        class Thing(BaseNode):
            name: complex

    ModelManager.initialise_models(_defined_in_test=True)
"""


def test_model_field_definition_with_literal_type():
    class Thing(BaseNode):
        name: str
        age: typing.Annotated[int, annotated_types.Gt(2), annotated_types.Le(3)]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["name"] == LiteralFieldDefinition(
        field_annotated_type=str, validators=[], field_name="name"
    )
    assert Thing.field_definitions["age"] == LiteralFieldDefinition(
        field_annotated_type=int,
        validators=[annotated_types.Gt(2), annotated_types.Le(3)],
        field_name="age",
    )


def test_model_field_definition_with_enum_type():
    class Status(enum.Enum):
        good = "good"
        shite = "shite"
        indifferent = 0

    class Thing(BaseNode):
        status: Status

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["status"] == LiteralFieldDefinition(
        field_annotated_type=Status, validators=[], field_name="status"
    )


def test_model_field_definition_with_literal_list_type():
    class Thing(BaseNode):
        names: list[str]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["names"] == ListFieldDefinition(
        field_annotated_type=str,
        field_name="names",
    )


def test_model_field_definition_raises_error_with_union_of_literal_types():
    class Thing(BaseNode):
        value: str | int

    with pytest.raises(PanglossConfigError):
        ModelManager.initialise_models(_defined_in_test=True)


def test_model_field_definition_with_embedded_type():
    class Thing(BaseNode):
        embedded_thing: Embedded[InnerThing]

    class InnerThing(BaseNode):
        pass

    class SecondThing(BaseNode):
        embedded_thing: Embedded[InnerThing | SecondInnerThing]

    class SecondInnerThing(BaseNode):
        pass

    class ThirdThing(BaseNode):
        embedded_thing: typing.Annotated[
            Embedded[InnerThing], annotated_types.MaxLen(2)
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["embedded_thing"] == EmbeddedFieldDefinition(
        field_name="embedded_thing",
        field_annotated_type=InnerThing,
        validators=[annotated_types.MinLen(1), annotated_types.MaxLen(1)],
    )

    assert SecondThing.field_definitions["embedded_thing"] == EmbeddedFieldDefinition(
        field_annotated_type=InnerThing | SecondInnerThing,
        field_name="embedded_thing",
        validators=[annotated_types.MinLen(1), annotated_types.MaxLen(1)],
    )

    assert ThirdThing.field_definitions["embedded_thing"] == EmbeddedFieldDefinition(
        field_annotated_type=InnerThing,
        field_name="embedded_thing",
        validators=[annotated_types.MaxLen(2)],
    )


def test_model_field_definition_with_basic_relation():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing, RelationConfig(reverse_name="has_reverse_relation_to")
        ]

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["related_to"] == RelationFieldDefinition(
        field_name="related_to",
        field_annotated_type=RelatedThing,
        reverse_name="has_reverse_relation_to",
    )


def test_model_field_definition_with_missing_relation_config_raises_error():
    class Thing(BaseNode):
        related_to: RelatedThing

    class RelatedThing(BaseNode):
        pass

    with pytest.raises(PanglossConfigError):
        ModelManager.initialise_models(_defined_in_test=True)


def test_model_field_definition_with_union_type():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing | OtherRelatedThing,
            RelationConfig(reverse_name="has_reverse_relation_to"),
        ]

    class RelatedThing(BaseNode):
        pass

    class OtherRelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["related_to"] == RelationFieldDefinition(
        field_annotated_type=RelatedThing | OtherRelatedThing,
        reverse_name="has_reverse_relation_to",
        field_name="related_to",
    )


def test_model_field_definition_with_reified_relation():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            Identification[RelatedThing],
            RelationConfig(reverse_name="has_reverse_relation_to"),
        ]

    class Identification[T](ReifiedRelation[T]):
        pass

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["related_to"] == RelationFieldDefinition(
        reverse_name="has_reverse_relation_to",
        field_annotated_type=Identification[RelatedThing],
        field_name="related_to",
    )


def test_model_field_definition_with_union_of_reified_relations():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            Identification[RelatedThing] | ActsOnBehalfOf[Identification[RelatedThing]],
            RelationConfig(reverse_name="has_reverse_relation_to"),
        ]

    class Identification[T](ReifiedRelation[T]):
        pass

    class ActsOnBehalfOf[T](ReifiedRelation[T]):
        pass

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["related_to"] == RelationFieldDefinition(
        field_name="related_to",
        reverse_name="has_reverse_relation_to",
        field_annotated_type=Identification[RelatedThing]
        | ActsOnBehalfOf[Identification[RelatedThing]],
    )


def test_model_field_definition_with_heritable_trait():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            Relatable, RelationConfig("has_reverse_relation_to_thing")
        ]

    class Relatable(HeritableTrait):
        pass

    class RelatedThing(BaseNode, Relatable):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["related_to"] == RelationFieldDefinition(
        field_name="related_to",
        field_annotated_type=Relatable,
        reverse_name="has_reverse_relation_to_thing",
    )


def test_model_field_definition_with_nonheritable_trait():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            Relatable, RelationConfig("has_reverse_relation_to_thing")
        ]

    class Relatable(NonHeritableTrait):
        pass

    class RelatedThing(BaseNode, Relatable):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.field_definitions["related_to"] == RelationFieldDefinition(
        field_name="related_to",
        field_annotated_type=Relatable,
        reverse_name="has_reverse_relation_to_thing",
    )


def test_delete_indirect_non_heritable_fields():
    class Trait(NonHeritableTrait):
        trait_field: str

    class Thing(BaseNode, Trait):
        thing_field: str

    class SubThing(Thing):
        sub_thing_field: str

    ModelManager.initialise_models(_defined_in_test=True)

    thing_fields = set(Thing.model_fields.keys())

    assert "thing_field" in thing_fields
    assert "trait_field" in thing_fields

    assert "thing_field" in Thing.field_definitions
    assert "trait_field" in Thing.field_definitions

    subthing_fields = set(SubThing.model_fields.keys())

    assert "thing_field" in subthing_fields
    assert "sub_thing_field" in subthing_fields
    assert "trait_field" not in subthing_fields

    assert "thing_field" in SubThing.field_definitions
    assert "sub_thing_field" in SubThing.field_definitions
    assert "trait_field" not in SubThing.field_definitions


def test_field_definition_field_concrete_type_set_up_correctly():
    class Thing(BaseNode):
        pass

    class OtherThing(BaseNode):
        pass

    class ThingOwner(BaseNode):
        thing_owned: typing.Annotated[
            Thing | OtherThing, RelationConfig(reverse_name="is_owned_by")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    thing_owned_definition = ThingOwner.field_definitions["thing_owned"]

    assert isinstance(thing_owned_definition, RelationFieldDefinition)
    assert thing_owned_definition.field_concrete_types == set([Thing, OtherThing])
