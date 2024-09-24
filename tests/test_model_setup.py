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
    EdgeModel,
    ReifiedRelation,
    Embedded,
    ViewBase,
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


def test_construct_specialised_reference_set_model_with_edge_properties():
    class ThingToRelatedThingPropertiesModel(EdgeModel):
        type_of_relation: str

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="is_related_to",
                edge_model=ThingToRelatedThingPropertiesModel,
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
        .model_fields["edge_properties"]
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


def test_initialise_relation_field_on_model_with_create_inline_with_edge_properties():
    class ThingToRelatedThingPropertiesModel(EdgeModel):
        type_of_relation: str

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="is_related_to",
                create_inline=True,
                edge_model=ThingToRelatedThingPropertiesModel,
            ),
        ]

    class RelatedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert (
        typing.get_args(Thing.model_fields["related_to"].annotation)[0].__name__
        == "Thing__related_to__RelatedThing__CreateInline"
    )


def test_initialise_reified_edge_model():
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


def test_initialise_reified_edge_model_with_dual_generic():
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


def test_initialise_reified_edge_model_with_double_reified():
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

    class IdentificationCertainty(EdgeModel):
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
    class ThingIdentificationRelationProperties(EdgeModel):
        type_of_thing: str

    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class Thing(BaseNode):
        related_to: typing.Annotated[
            Identification[RelatedThing],
            RelationConfig(
                reverse_name="is_related_to",
                edge_model=ThingIdentificationRelationProperties,
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

    assert typing.get_args(related_to_annotation)[0].model_fields["edge_properties"]
    assert (
        typing.get_args(related_to_annotation)[0]
        .model_fields["edge_properties"]
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


def test_initialise_view_type_for_base_with_reified_relation_is_all_view_types():
    """Go through all the `target` arguments to check that they are all view types"""

    class Identification[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Identification[Person], RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Event.View.model_fields["person_involved"]

    origin_type = typing.get_origin(
        Event.View.model_fields["person_involved"].annotation
    )
    assert origin_type == list

    arg_type = typing.get_args(Event.View.model_fields["person_involved"].annotation)[0]
    assert issubclass(arg_type, pydantic.BaseModel)
    assert (
        arg_type.__name__
        == "Identification[test_initialise_view_type_for_base_with_reified_relation_is_all_view_types.<locals>.Person]View"
    )
    assert issubclass(arg_type, ViewBase)

    assert arg_type.model_fields["target"].annotation

    target_origin_type = typing.get_origin(arg_type.model_fields["target"].annotation)
    assert target_origin_type == list

    target_arg_type = typing.get_args(arg_type.model_fields["target"].annotation)[0]

    assert issubclass(target_arg_type, ReferenceViewBase)

    assert target_arg_type == Person.ReferenceView


def test_initialise_view_type_for_base():
    class Identification[T](ReifiedRelation[T]):
        pass

    class ToIdentification(EdgeModel):
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
                reverse_name="has_also_relation_to", edge_model=ToIdentification
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

    also_related_to_args_names = set(
        arg.__name__
        for arg in typing.get_args(
            typing.get_args(Thing.View.model_fields["also_related_to"].annotation)[0]
        )
    )

    assert (
        "Thing__also_related_to__RelatedThing__ReferenceView"
        in also_related_to_args_names
    )
    assert (
        "Thing__also_related_to__Identification[test_initialise_view_type_for_base.<locals>.RelatedThing]__View"
        in also_related_to_args_names
    )

    embedded_thing_args = typing.get_args(
        Thing.View.model_fields["embedded_thing"].annotation
    )
    assert embedded_thing_args[0] == EmbeddedThing.EmbeddedView


def test_view_initialisation_of_reverse_relation():
    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.View.model_fields["is_involved_in"]

    is_involved_in_model = Person.View.model_fields["is_involved_in"]

    assert is_involved_in_model.annotation == list[Event.ReferenceView]


def test_view_initialisation_of_reverse_relation_with_multiple_sources():
    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    class Party(BaseNode):
        person_partying: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.View.model_fields["is_involved_in"]

    is_involved_in_model = Person.View.model_fields["is_involved_in"]

    assert (
        is_involved_in_model.annotation
        == list[Event.ReferenceView | Party.ReferenceView]
    )


def test_view_initialisation_with_reverse_relation_with_reified_relation_simple():
    class IgnorableThing(BaseNode):
        pass

    class Identification[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Identification[Person],
            RelationConfig(reverse_name="is_involved_in"),
        ]
        should_not_be_there: str

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.View.model_fields["is_involved_in"]

    is_involved_in = Person.View.model_fields["is_involved_in"]

    assert typing.get_origin(is_involved_in.annotation) == list

    assert (
        typing.get_args(is_involved_in.annotation)[0].__name__
        == "Event__from__person_involved__Person__View"
    )

    source_class = typing.get_args(is_involved_in.annotation)[0]

    assert issubclass(source_class, ViewBase)
    assert source_class.__name__ == "Event__from__person_involved__Person__View"

    assert "person_involved" in source_class.model_fields.keys()
    assert "should_not_be_there" not in source_class.model_fields.keys()

    event_person_involved = source_class.model_fields["person_involved"]
    # TODO: verify properly here...

    assert typing.get_origin(event_person_involved.annotation) == list

    assert typing.get_args(event_person_involved.annotation)[0]

    identification_person = typing.get_args(event_person_involved.annotation)[0]

    assert issubclass(identification_person, ViewBase)


def test_view_initialisation_of_reverse_relation_with_reified_relation_complex():
    """Test initialisation of model with reverse relations, so that reverse
    relation points to target or otherwise point of attachment to chain;

    and, that everything all the way down is a View type"""

    class Person(BaseNode):
        pass

    class Identification[T](ReifiedRelation[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]

    class WithProxyActor[T, U](ReifiedRelationNode[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
        proxy: typing.Annotated[U, RelationConfig(reverse_name="acts_as_proxy_in")]

    class Event(BaseNode):
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person], Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.View.model_fields["is_carried_out_by"]

    is_carried_out_by = Person.View.model_fields["is_carried_out_by"].annotation

    # Check type is wrapped in a list
    assert typing.get_origin(is_carried_out_by) == list

    # Get inner type and check it has correct name
    is_carried_out_by_type = typing.get_args(is_carried_out_by)[0]

    assert (
        is_carried_out_by_type.__name__ == "Event__from__carried_out_by__Person__View"
    )

    assert issubclass(is_carried_out_by_type, ViewBase)

    assert "carried_out_by" in is_carried_out_by_type.model_fields.keys()

    # Now check the carried_out_by field to check it's also a View type
    assert is_carried_out_by_type.model_fields["carried_out_by"].annotation

    event_carried_out_by = is_carried_out_by_type.model_fields[
        "carried_out_by"
    ].annotation

    assert typing.get_origin(event_carried_out_by) == list

    event_carried_out_by_type = typing.get_args(event_carried_out_by)[0]

    assert issubclass(event_carried_out_by_type, ViewBase)

    with_proxy_actor = event_carried_out_by_type

    assert with_proxy_actor.model_fields["target"]

    # Quickly check the "proxy" path here
    assert with_proxy_actor.model_fields["proxy"]
    with_proxy_proxy = typing.get_args(
        with_proxy_actor.model_fields["proxy"].annotation
    )[0]
    assert issubclass(with_proxy_proxy, ViewBase)

    with_proxy_actor_target = with_proxy_actor.model_fields["target"].annotation

    assert typing.get_origin(with_proxy_actor_target) == list

    with_proxy_actor_target_type = typing.get_args(with_proxy_actor_target)[0]

    assert issubclass(with_proxy_actor_target_type, ViewBase)

    assert with_proxy_actor_target_type.model_fields["target"]

    identification = with_proxy_actor_target_type.model_fields["target"].annotation

    assert typing.get_origin(identification) == list

    person_type = typing.get_args(identification)[0]

    assert person_type == Person.ReferenceView

    # Now check the "acts_as_proxy" field, which should also be an event
    assert Person.View.model_fields["acts_as_proxy_in"]

    assert Person.View.model_fields["acts_as_proxy_in"].annotation

    assert (
        typing.get_origin(Person.View.model_fields["acts_as_proxy_in"].annotation)
        == list
    )

    acts_as_proxy_in_type = typing.get_args(
        Person.View.model_fields["acts_as_proxy_in"].annotation
    )[0]

    assert acts_as_proxy_in_type.__name__ == "Event__from__proxy__Person__View"

    assert issubclass(acts_as_proxy_in_type, ViewBase)

    assert acts_as_proxy_in_type.model_fields["carried_out_by"]

    event_carried_out_by = acts_as_proxy_in_type.model_fields[
        "carried_out_by"
    ].annotation

    assert typing.get_origin(event_carried_out_by) == list

    event_carried_out_by_type = typing.get_args(event_carried_out_by)[0]

    assert issubclass(event_carried_out_by_type, ViewBase)

    with_proxy_actor = event_carried_out_by_type

    assert with_proxy_actor.model_fields["target"]

    # Quickly check the "proxy" path here
    assert with_proxy_actor.model_fields["proxy"]
    with_proxy_proxy = typing.get_args(
        with_proxy_actor.model_fields["proxy"].annotation
    )[0]
    assert issubclass(with_proxy_proxy, ViewBase)

    with_proxy_actor_target = with_proxy_actor.model_fields["target"].annotation

    assert typing.get_origin(with_proxy_actor_target) == list

    with_proxy_actor_target_type = typing.get_args(with_proxy_actor_target)[0]

    assert issubclass(with_proxy_actor_target_type, ViewBase)

    assert with_proxy_actor_target_type.model_fields["target"]

    identification = with_proxy_actor_target_type.model_fields["target"].annotation

    assert typing.get_origin(identification) == list

    person_type = typing.get_args(identification)[0]

    assert person_type == Person.ReferenceView


def test_view_initialisation_of_reverse_relation_with_reified_relation_complex_with_edge_model():
    class Certainty(EdgeModel):
        certainty: int

    class Person(BaseNode):
        pass

    T = typing.TypeVar("T")
    U = typing.TypeVar("U")

    class Identification(ReifiedRelation[T]):
        target: typing.Annotated[
            T, RelationConfig(reverse_name="is_target_of", edge_model=Certainty)
        ]

    class WithProxyActor(ReifiedRelationNode[T], typing.Generic[T, U]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
        proxy: typing.Annotated[U, RelationConfig(reverse_name="acts_as_proxy_in")]

    class Event(BaseNode):
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person], Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.View.model_fields["is_carried_out_by"]

    is_carried_out_by = typing.get_args(
        Person.View.model_fields["is_carried_out_by"].annotation
    )[0]
    assert issubclass(is_carried_out_by, ViewBase)

    assert is_carried_out_by.model_fields["edge_properties"]

    assert is_carried_out_by.model_fields["edge_properties"].annotation == Certainty


def test_initialise_edit_view():
    class Person(BaseNode):
        age: int

    class Event(BaseNode):
        event_type: str
        involves_person: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Event.EditView
    assert "event_type" in Event.EditView.model_fields

    assert "involves_person" in Event.EditView.model_fields
    assert (
        Event.EditView.model_fields["involves_person"].annotation
        == list[Person.ReferenceView]
    )

    assert "age" in Person.EditView.model_fields
    assert "is_involved_in" not in Person.EditView.model_fields

    assert "is_involved_in" in Person.View.model_fields

    assert Person.EditView.base_class == Person
    assert Event.EditView.base_class == Event


def test_initialise_edit_set_type_basic():
    class Event(BaseNode):
        event_type: str
        involves_person: typing.Annotated[
            Person,
            RelationConfig(reverse_name="is_involved_in"),
            annotated_types.MaxLen(1),
        ]
        involves_person_edit_inline: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in", edit_inline=True)
        ]

    class Person(BaseNode):
        age: int

    ModelManager.initialise_models(_defined_in_test=True)

    assert Event.EditSet

    assert "event_type" in Event.EditSet.model_fields

    assert "involves_person" in Event.EditSet.model_fields

    assert (
        Event.EditSet.model_fields["involves_person"].annotation
        == list[Person.ReferenceSet]
    )
    assert Event.EditSet.model_fields["involves_person"].metadata == [
        annotated_types.MaxLen(1)
    ]


def test_initialise_edit_set_type_with_cyclical_relation():
    class DoubleIntermediate(BaseNode):
        double_intermediate_target: typing.Annotated[
            Intermediate,
            Order,
            DoubleIntermediate,
            RelationConfig(
                reverse_name="is_invovled_in_double_intermediate", edit_inline=True
            ),
        ]

    class Order(BaseNode):
        thing_ordered: typing.Annotated[
            typing.Union[Payment, Intermediate, DoubleIntermediate],
            RelationConfig(
                reverse_name="was_ordered_in",
                edit_inline=True,
                validators=[annotated_types.MaxLen(2)],
            ),
        ]

    class Intermediate(BaseNode):
        intermediate_target: typing.Annotated[
            Order,
            RelationConfig(reverse_name="is_person_in", edit_inline=True),
        ]

    class Payment(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert (
        Order.EditSet.model_fields["thing_ordered"].annotation
        == list[
            typing.Union[
                DoubleIntermediate,
                DoubleIntermediate.EditSet,
                Payment,
                Payment.EditSet,
                Intermediate,
                Intermediate.EditSet,
            ]
        ]
    )

    assert Order.EditSet.model_fields["thing_ordered"].metadata == [
        annotated_types.MaxLen(2)
    ]


def test_initialise_edit_with_embedded_node():
    class Thing(BaseNode):
        embedded: Embedded[EmbeddedThing]

    class EmbeddedThing(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert (
        Thing.EditSet.model_fields["embedded"].annotation
        == list[typing.Union[EmbeddedThing, EmbeddedThing.EditSet]]
    )

    assert Thing.EditSet.model_fields["embedded"].metadata == [
        annotated_types.MinLen(1),
        annotated_types.MaxLen(1),
    ]
