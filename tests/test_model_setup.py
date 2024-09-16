from __future__ import annotations

import pytest

import typing

import annotated_types
import pydantic

from pangloss.exceptions import PanglossConfigError
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_utils import is_subclass_of_heritable_trait
from pangloss.model_config.model_setup_functions import (
    create_embedded_set_model,
    initialise_reference_set_on_base_models,
    initialise_reference_view_on_base_models,
    initialise_reified_relation,
)
from pangloss.model_config.models_base import (
    ReferenceSetBase,
    ReferenceViewBase,
    ReifiedRelationNode,
    RelationPropertiesModel,
    ReifiedRelation,
    Embedded,
)
from pangloss.model_config.field_definitions import (
    LiteralFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.models import BaseNode, HeritableTrait, RelationConfig


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


def test_abstract_declaration_not_inherited():
    class Thing(BaseNode):
        __abstract__ = True

    class Animal(Thing):
        pass

    class Pet(Animal):
        __abstract__ = True

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.__abstract__
    assert not Animal.__abstract__
    assert Pet.__abstract__


def test_model_is_subclass_of_trait():
    class Relatable(HeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    assert is_subclass_of_heritable_trait(VeryRelatable)

    assert not is_subclass_of_heritable_trait(Thing)


def test_initialise_reference_set_on_models_function():
    class Thing(BaseNode):
        name: str
        age: int

    class OtherThing(BaseNode):
        name: str
        age: int

        class ReferenceSet(ReferenceSetBase):
            name: str

    class BrokenThingA(BaseNode):
        name: str

        class ReferenceSet:  # <-- Does not inherit from ReferenceSetBase
            name: str

    initialise_reference_set_on_base_models(Thing)

    assert Thing.ReferenceSet
    assert set(Thing.ReferenceSet.model_fields.keys()) == set(["type", "uuid"])
    assert Thing.ReferenceSet.model_fields["type"].annotation == typing.Literal["Thing"]
    assert Thing.ReferenceSet.model_fields["type"].default == "Thing"

    initialise_reference_set_on_base_models(OtherThing)

    assert OtherThing.ReferenceSet
    assert set(OtherThing.ReferenceSet.model_fields.keys()) == set(
        ["name", "type", "uuid"]
    )
    assert (
        OtherThing.ReferenceSet.model_fields["type"].annotation
        == typing.Literal["OtherThing"]
    )

    with pytest.raises(PanglossConfigError):
        initialise_reference_set_on_base_models(BrokenThingA)


def test_initialise_reference_set_on_models_during_model_setup():
    class NewThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert NewThing.ReferenceSet
    assert set(NewThing.ReferenceSet.model_fields.keys()) == set(["type", "uuid"])
    assert (
        NewThing.ReferenceSet.model_fields["type"].annotation
        == typing.Literal["NewThing"]
    )
    assert NewThing.ReferenceSet.model_fields["type"].default == "NewThing"


def test_initialise_reference_view_on_models_function():
    class Thing(BaseNode):
        name: str
        age: int

    class OtherThing(BaseNode):
        name: str
        age: int

        class ReferenceView(ReferenceViewBase):
            name: str

    class BrokenThingA(BaseNode):
        name: str

        class ReferenceView:  # <-- Does not inherit from ReferenceSetBase
            name: str

    initialise_reference_view_on_base_models(Thing)

    assert Thing.ReferenceView
    assert set(Thing.ReferenceView.model_fields.keys()) == set(
        ["type", "uuid", "label"]
    )
    assert (
        Thing.ReferenceView.model_fields["type"].annotation == typing.Literal["Thing"]
    )
    assert Thing.ReferenceView.model_fields["type"].default == "Thing"

    initialise_reference_view_on_base_models(OtherThing)

    assert OtherThing.ReferenceView
    assert set(OtherThing.ReferenceView.model_fields.keys()) == set(
        ["type", "uuid", "label", "name"]
    )
    assert (
        OtherThing.ReferenceView.model_fields["type"].annotation
        == typing.Literal["OtherThing"]
    )
    assert OtherThing.ReferenceView.model_fields["type"].default == "OtherThing"

    with pytest.raises(PanglossConfigError):
        initialise_reference_view_on_base_models(BrokenThingA)


def test_initialise_reference_view_on_models_during_model_setup():
    class NewThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert NewThing.ReferenceView
    assert set(NewThing.ReferenceView.model_fields.keys()) == set(
        ["type", "uuid", "label"]
    )
    assert (
        NewThing.ReferenceView.model_fields["type"].annotation
        == typing.Literal["NewThing"]
    )
    assert NewThing.ReferenceView.model_fields["type"].default == "NewThing"


def test_initialise_basic_relation_field_on_model():
    class RelatedThing(BaseNode):
        pass

    class SubRelatedThing(RelatedThing):
        pass

    class OtherRelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing | OtherRelatedThing,
            RelationConfig(
                reverse_name="is_related_to", validators=[annotated_types.MaxLen(10)]
            ),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert (
        Thing.model_fields["related_to"].annotation
        == list[
            RelatedThing.ReferenceSet
            | SubRelatedThing.ReferenceSet
            | OtherRelatedThing.ReferenceSet
        ]
    )

    assert annotated_types.MaxLen(10) in Thing.model_fields["related_to"].metadata


def test_construct_specialised_reference_set_model_with_relation_properties():
    class ThingToRelatedThingPropertiesModel(RelationPropertiesModel):
        type_of_relation: str

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="is_related_to",
                relation_model=ThingToRelatedThingPropertiesModel,
            ),
        ]

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    related_to_annotation = Thing.model_fields["related_to"].annotation
    assert related_to_annotation
    assert typing.get_origin(related_to_annotation) == list
    assert (
        typing.get_args(related_to_annotation)[0].__name__
        == "Thing__related_to__RelatedThing__ReferenceSet"
    )
    assert issubclass(typing.get_args(related_to_annotation)[0], pydantic.BaseModel)
    assert (
        typing.get_args(related_to_annotation)[0]
        .model_fields["relation_properties"]
        .annotation
        == ThingToRelatedThingPropertiesModel
    )


def test_initialise_relation_field_on_model_with_create_inline():
    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(reverse_name="is_related_to", create_inline=True),
        ]

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.model_fields["related_to"].annotation == list[RelatedThing]


def test_initialise_relation_field_on_model_with_create_inline_with_relation_properties():
    class ThingToRelatedThingPropertiesModel(RelationPropertiesModel):
        type_of_relation: str

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="is_related_to",
                create_inline=True,
                relation_model=ThingToRelatedThingPropertiesModel,
            ),
        ]

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert (
        typing.get_args(Thing.model_fields["related_to"].annotation)[0].__name__
        == "Thing__related_to__RelatedThing__CreateInline"
    )


def test_initialise_reified_relation_model():
    class Identification[T](ReifiedRelation[T]):
        certainty: int
        points_to_other_thing: typing.Annotated[
            OtherThing, RelationConfig(reverse_name="is_pointed_to_by_identification")
        ]

    class IdentifiedThing(BaseNode):
        pass

    class OtherIdentifiedThing(BaseNode):
        pass

    class OtherThing(BaseNode):
        pass

    reified_relation = Identification[IdentifiedThing | OtherIdentifiedThing]

    ModelManager.initialise_models(_defined_in_test=True)

    initialise_reified_relation(reified_relation)

    assert reified_relation.field_definitions
    assert reified_relation.field_definitions["certainty"] == LiteralFieldDefinition(
        field_name="certainty",
        field_annotated_type=int,
    )
    assert reified_relation.field_definitions[
        "points_to_other_thing"
    ] == RelationFieldDefinition(
        field_name="points_to_other_thing",
        field_annotated_type=OtherThing,
        reverse_name="is_pointed_to_by_identification",
    )
    assert reified_relation.field_definitions["target"] == RelationFieldDefinition(
        field_name="target",
        field_annotated_type=IdentifiedThing | OtherIdentifiedThing,
        reverse_name="is_target_of",
    )

    """ Thinking out loud:
        reification needs its fields initialised
        so needs a field_definition so it can handle things? Yes probably
        
        but this cannot be done ahead of time, as generic type means
        it doesn't really really exist until use by some class...
        
        *should* if carefully done be able to use previous base_model initting functions?
    """


def test_initialise_reified_relation_model_with_dual_generic():
    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class SubIdentification[U, T](Identification[T]):
        points_to_other_thing: typing.Annotated[
            U, RelationConfig(reverse_name="is_pointed_to_by_identification")
        ]

    class IdentifiedThing(BaseNode):
        pass

    class OtherIdentifiedThing(BaseNode):
        pass

    class OtherThing(BaseNode):
        pass

    reified_relation = SubIdentification[
        OtherThing, IdentifiedThing | OtherIdentifiedThing
    ]

    ModelManager.initialise_models(_defined_in_test=True)

    initialise_reified_relation(reified_relation)

    assert reified_relation.field_definitions["target"] == RelationFieldDefinition(
        field_name="target",
        field_annotated_type=IdentifiedThing | OtherIdentifiedThing,
        reverse_name="is_target_of",
    )
    assert reified_relation.field_definitions[
        "points_to_other_thing"
    ] == RelationFieldDefinition(
        field_name="points_to_other_thing",
        field_annotated_type=OtherThing,
        reverse_name="is_pointed_to_by_identification",
    )


def test_initialise_reified_relation_model_with_double_reified():
    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class ForwardedIdentification[T](ReifiedRelation[T]):
        pass

    class IdentifiedThing(BaseNode):
        pass

    reified_relation = Identification[ForwardedIdentification[IdentifiedThing]]

    ModelManager.initialise_models(_defined_in_test=True)

    initialise_reified_relation(reified_relation)

    assert reified_relation.field_definitions["target"] == RelationFieldDefinition(
        field_name="target",
        field_annotated_type=ForwardedIdentification[IdentifiedThing],
        reverse_name="is_target_of",
    )

    assert ForwardedIdentification[IdentifiedThing].field_definitions[
        "target"
    ] == RelationFieldDefinition(
        field_name="target",
        field_annotated_type=IdentifiedThing,
        reverse_name="is_target_of",
    )

    assert (
        typing.get_origin(
            ForwardedIdentification[IdentifiedThing].model_fields["target"].annotation
        )
        == list
    )
    assert (
        typing.get_args(
            ForwardedIdentification[IdentifiedThing].model_fields["target"].annotation
        )[0].__name__
        == "IdentifiedThingReferenceSet"
    )


def test_initialise_reified_relation_with_overridden_type_t():
    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class ForwardedIdentification[T, U](ReifiedRelation[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
        other: typing.Annotated[U, RelationConfig(reverse_name="is_other_of")]

    class IdentifiedThing(BaseNode):
        pass

    class OtherIdentifiedThing(BaseNode):
        pass

    reified_relation = Identification[
        ForwardedIdentification[IdentifiedThing, OtherIdentifiedThing]
    ]

    ModelManager.initialise_models(_defined_in_test=True)

    initialise_reified_relation(reified_relation)

    assert reified_relation.model_fields["target"].annotation
    assert typing.get_args(reified_relation.model_fields["target"].annotation)[0]
    assert (
        typing.get_args(
            typing.get_args(reified_relation.model_fields["target"].annotation)[0]
            .model_fields["target"]
            .annotation
        )[0]
        == IdentifiedThing.ReferenceSet
    )


def test_initialise_reified_relation_with_reified_node():
    class Person(BaseNode):
        pass

    class IdentificationCertainty(RelationPropertiesModel):
        certainty: int

    class Identification[T](ReifiedRelation[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]

    class WithProxyActor[T](ReifiedRelationNode[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
        proxy: typing.Annotated[T, RelationConfig(reverse_name="acts_as_proxy_in")]

    class Event(BaseNode):
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    event_carried_out_by = Event.model_fields["carried_out_by"]
    assert event_carried_out_by
    assert typing.get_origin(event_carried_out_by.annotation) == list
    assert typing.get_args(event_carried_out_by.annotation)[0]

    assert issubclass(
        typing.get_args(event_carried_out_by.annotation)[0], WithProxyActor
    )


def test_initialise_reified_relation_with_relation_property_model():
    class ThingIdentificationRelationProperties(RelationPropertiesModel):
        type_of_thing: str

    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class Thing(BaseNode):
        related_to: typing.Annotated[
            Identification[RelatedThing],
            RelationConfig(
                reverse_name="is_related_to",
                relation_model=ThingIdentificationRelationProperties,
            ),
        ]

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    related_to_annotation = Thing.model_fields["related_to"].annotation
    assert typing.get_origin(related_to_annotation) == list
    assert (
        typing.get_args(related_to_annotation)[0].__name__
        == "Thing__related_to__Identification[test_initialise_reified_relation_with_relation_property_model.<locals>.RelatedThing]"
    )

    assert typing.get_args(related_to_annotation)[0].model_fields["relation_properties"]
    assert (
        typing.get_args(related_to_annotation)[0]
        .model_fields["relation_properties"]
        .annotation
        == ThingIdentificationRelationProperties
    )


def test_create_embedded_set_node_type():
    class RelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        name: str
        age: int
        related_to: typing.Annotated[
            RelatedThing, RelationConfig(reverse_name="has_related_thing")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    embedded_set_model = create_embedded_set_model(Thing)

    with pytest.raises(KeyError):
        embedded_set_model.model_fields["label"]

    assert embedded_set_model.model_fields["name"].annotation == str
    assert embedded_set_model.model_fields["age"].annotation == int
    assert (
        embedded_set_model.model_fields["related_to"].annotation
        == list[RelatedThing.ReferenceSet]
    )


def test_initialise_embedded_node_on_base_model():
    class Thing(BaseNode):
        embedded_thing: Embedded[InnerThing]

    class InnerThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert (
        Thing.model_fields["embedded_thing"].annotation == list[InnerThing.EmbeddedSet]
    )
    assert Thing.model_fields["embedded_thing"].metadata == [
        annotated_types.MinLen(1),
        annotated_types.MaxLen(1),
    ]


def test_initialise_view_type_for_base():
    class Identification[T](ReifiedRelation[T]):
        pass

    class ToIdentification(RelationPropertiesModel):
        something: str

    class Thing(BaseNode):
        name: typing.Annotated[str, annotated_types.MaxLen(10)]
        age: int
        related_to: typing.Annotated[
            RelatedThing | Identification[RelatedThing],
            RelationConfig(reverse_name="has_reverse_relation_to"),
        ]
        also_related_to: typing.Annotated[
            RelatedThing | Identification[RelatedThing],
            RelationConfig(
                reverse_name="has_also_relation_to", relation_model=ToIdentification
            ),
        ]
        embedded_thing: Embedded[EmbeddedThing]

    class RelatedThing(BaseNode):
        pass

    class EmbeddedThing(BaseNode):
        stuff: str

    ModelManager.initialise_models(_defined_in_test=True)

    assert Thing.View.model_fields["name"].annotation == str
    assert Thing.View.model_fields["name"].metadata == [annotated_types.MaxLen(10)]
    assert Thing.View.model_fields["age"].annotation == int
    assert (
        Thing.View.model_fields["related_to"].annotation
        == list[RelatedThing.ReferenceView | Identification[RelatedThing].View]
    )

    also_related_to_args = set(
        arg.__name__
        for arg in typing.get_args(
            typing.get_args(Thing.View.model_fields["also_related_to"].annotation)[0]
        )
    )

    assert "Thing__also_related_to__RelatedThing__ReferenceView" in also_related_to_args
    assert (
        "Thing__also_related_to__Identification[test_initialise_view_type_for_base.<locals>.RelatedThing]__View"
        in also_related_to_args
    )

    embedded_thing_args = typing.get_args(
        Thing.View.model_fields["embedded_thing"].annotation
    )
    assert embedded_thing_args[0] == EmbeddedThing.EmbeddedView
