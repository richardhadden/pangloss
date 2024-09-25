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
    MultiKeyFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.models_base import (
    NonHeritableTrait,
    ReifiedRelationNode,
    EdgeModel,
    MultiKeyField,
)
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


def test_embedded_field_definition_builds_concrete_types_on_init():
    class InnerThing(BaseNode):
        pass

    class OtherInnerThing(BaseNode):
        pass

    embedded_definition = EmbeddedFieldDefinition(
        field_name="embedded_thing", field_annotated_type=InnerThing | OtherInnerThing
    )

    assert embedded_definition.field_concrete_types == set(
        [InnerThing, OtherInnerThing]
    )


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


def test_model_field_definition_with_reified_node():
    class Person(BaseNode):
        pass

    class IdentificationCertainty(EdgeModel):
        certainty: int

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

    assert Event.field_definitions["carried_out_by"]
    carried_out_by_definition = Event.field_definitions["carried_out_by"]
    assert isinstance(carried_out_by_definition, RelationFieldDefinition)

    with_proxy_actor = carried_out_by_definition.field_concrete_types.pop()

    assert issubclass(with_proxy_actor, WithProxyActor)

    assert with_proxy_actor.field_definitions["target"]
    with_proxy_actor_target_definition = with_proxy_actor.field_definitions["target"]

    assert isinstance(with_proxy_actor_target_definition, RelationFieldDefinition)

    identification = with_proxy_actor_target_definition.field_concrete_types.pop()

    assert identification
    assert issubclass(identification, Identification)

    assert identification.field_definitions["target"]

    identification_target_definition = identification.field_definitions["target"]

    assert isinstance(identification_target_definition, RelationFieldDefinition)

    person = identification_target_definition.field_concrete_types.pop()

    assert person
    assert issubclass(person, Person)


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


def test_incoming_relation_definition_for_simple_relation():
    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.incoming_relation_definitions["is_involved_in"]

    is_involved_in = Person.incoming_relation_definitions["is_involved_in"].pop()

    assert is_involved_in.field_name == "person_involved"
    assert is_involved_in.reverse_name == "is_involved_in"

    assert is_involved_in.target_type == Person
    assert is_involved_in.source_type == Event
    assert is_involved_in.source_concrete_type == Event.ReferenceView


def test_incoming_relation_definition_with_relation_from_multiple():
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

    assert Person.incoming_relation_definitions["is_involved_in"]

    assert len(Person.incoming_relation_definitions["is_involved_in"]) == 2

    involved_in_event = [
        rel_def
        for rel_def in Person.incoming_relation_definitions["is_involved_in"]
        if rel_def.source_type == Event
    ][0]
    assert involved_in_event.field_name == "person_involved"
    assert involved_in_event.reverse_name == "is_involved_in"
    assert involved_in_event.target_type == Person
    assert involved_in_event.source_concrete_type == Event.ReferenceView

    involved_in_party = [
        rel_def
        for rel_def in Person.incoming_relation_definitions["is_involved_in"]
        if rel_def.source_type == Party
    ][0]
    assert involved_in_party
    assert involved_in_party.field_name == "person_partying"
    assert involved_in_party.reverse_name == "is_involved_in"
    assert involved_in_party.target_type == Person
    assert involved_in_party.source_concrete_type == Party.ReferenceView


def test_incoming_relation_type_with_edge_model():
    class Notes(EdgeModel):
        note: str

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Person, RelationConfig(reverse_name="is_involved_in", edge_model=Notes)
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.incoming_relation_definitions["is_involved_in"]

    is_involved_in = Person.incoming_relation_definitions["is_involved_in"].pop()

    assert is_involved_in
    assert is_involved_in.field_name == "person_involved"
    assert is_involved_in.reverse_name == "is_involved_in"
    assert is_involved_in.target_type == Person
    assert is_involved_in.source_type == Event
    assert (
        is_involved_in.source_concrete_type.__name__
        == "Event__person_involved__Person__ReferenceView"
    )


def test_incoming_relation_definition_through_embedded():
    """Test that incoming relations (on Person) from an embedded node (Invitation embedded in Event) has
    relation from containing type (Event) as well as embedded type (Invitation)
    """

    class Person(BaseNode):
        pass

    class Invitation(BaseNode):
        invited_person: typing.Annotated[
            Person, RelationConfig(reverse_name="was_invited_to")
        ]

    class Event(BaseNode):
        invitations: Embedded[Invitation]

    ModelManager.initialise_models(_defined_in_test=True)

    # Incoming relation is defined to both Event and Invitation
    assert len(Person.incoming_relation_definitions["was_invited_to"]) == 2

    was_invited_to_event = [
        rel_def
        for rel_def in Person.incoming_relation_definitions["was_invited_to"]
        if rel_def.source_type == Event
    ][0]

    assert was_invited_to_event
    assert was_invited_to_event.field_name == "invited_person"
    assert was_invited_to_event.reverse_name == "was_invited_to"
    assert was_invited_to_event.target_type == Person
    assert was_invited_to_event.source_type == Event
    assert was_invited_to_event.source_concrete_type == Event.ReferenceView

    was_invited_to_invitation = [
        rel_def
        for rel_def in Person.incoming_relation_definitions["was_invited_to"]
        if rel_def.source_type == Invitation
    ][0]

    assert was_invited_to_invitation
    assert was_invited_to_invitation.field_name == "invited_person"
    assert was_invited_to_invitation.reverse_name == "was_invited_to"
    assert was_invited_to_invitation.target_type == Person
    assert was_invited_to_invitation.source_type == Invitation
    assert was_invited_to_invitation.source_concrete_type == Invitation.ReferenceView


def test_incoming_relation_definition_through_simple_reified_relation():
    class Identification[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Identification[Person],
            RelationConfig(reverse_name="is_involved_in"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.incoming_relation_definitions["is_involved_in"]
    assert len(Person.incoming_relation_definitions["is_involved_in"]) == 1

    is_involved_in_definition = Person.incoming_relation_definitions[
        "is_involved_in"
    ].pop()

    assert is_involved_in_definition
    assert is_involved_in_definition.field_name == "person_involved"
    assert is_involved_in_definition.reverse_name == "is_involved_in"
    assert is_involved_in_definition.target_type == Person
    assert is_involved_in_definition.source_type == Event
    assert (
        is_involved_in_definition.source_concrete_type.__name__
        == "Event__from__person_involved__Person__View"
    )

    source_concrete_type = is_involved_in_definition.source_concrete_type

    assert "person_involved" in source_concrete_type.model_fields.keys()


def test_incoming_relation_definition_through_double_reified_relation():
    class Identification1[T](ReifiedRelation[T]):
        pass

    class Identification2[T](ReifiedRelation[T]):
        pass

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        person_involved: typing.Annotated[
            Identification2[Identification1[Person]],
            RelationConfig(reverse_name="is_involved_in"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Person.incoming_relation_definitions["is_involved_in"]
    assert len(Person.incoming_relation_definitions["is_involved_in"]) == 1

    is_involved_in_definition = Person.incoming_relation_definitions[
        "is_involved_in"
    ].pop()
    assert is_involved_in_definition
    assert is_involved_in_definition.field_name == "person_involved"
    assert is_involved_in_definition.reverse_name == "is_involved_in"
    assert is_involved_in_definition.target_type == Person
    assert is_involved_in_definition.source_type == Event
    assert (
        is_involved_in_definition.source_concrete_type.__name__
        == "Event__from__person_involved__Person__View"
    )

    source_concrete_type = is_involved_in_definition.source_concrete_type

    assert "person_involved" in source_concrete_type.model_fields.keys()


def test_outgoing_relation_with_literal_union():
    """Test to figure out why typing.Union[A, B] is different to A | B"""

    class Event(BaseNode):
        carried_out_by: typing.Annotated[
            # Person | Organisation,
            typing.Union[Person, Organisation],
            RelationConfig(reverse_name="carried_out_event"),
        ]

    class Person(BaseNode):
        pass

    class Organisation(BaseNode):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    carried_out_by = Event.field_definitions["carried_out_by"]

    assert isinstance(carried_out_by, RelationFieldDefinition)

    assert carried_out_by.field_concrete_types == {Person, Organisation}


def test_multi_key_field_definition():
    class WithCertainty[T](MultiKeyField[T]):
        certainty: int

    class Thing(BaseNode):
        name: WithCertainty[str]

    ModelManager.initialise_models(_defined_in_test=True)

    assert "name" in Thing.field_definitions
    assert any(
        pf.field_name
        for pf in Thing.field_definitions.property_fields
        if pf.field_name == "name"
    )

    name_definition = Thing.field_definitions["name"]

    assert isinstance(name_definition, MultiKeyFieldDefinition)
