from __future__ import annotations

import pytest

import datetime
import typing
import uuid

import annotated_types
import pydantic

from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.models_base import (
    Embedded,
    MultiKeyField,
    ReifiedRelationNode,
)
from pangloss.models import (
    BaseNode,
    RelationConfig,
    EdgeModel,
    ReifiedRelation,
    HeritableTrait,
    NonHeritableTrait,
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
    class ThingRelatedThingRelation(EdgeModel):
        certainty: int

    class RelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing,
            RelationConfig(
                reverse_name="has_relation_to", edge_model=ThingRelatedThingRelation
            ),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Thing(
        label="A Thing",
        related_to=[
            {
                "type": "RelatedThing",
                "uuid": uuid.uuid4(),
                "edge_properties": {"certainty": 1},
            }
        ],
    )


@typing.no_type_check
def test_create_with_reified_relation():
    class IdentificationCertainty(EdgeModel):
        certainty: int

    class ThingToIdentifcation(EdgeModel):
        something: str

    T = typing.TypeVar("T")

    class Identification(ReifiedRelation[T]):
        target: typing.Annotated[
            T,
            RelationConfig(
                "is_target_of_identification",
                edge_model=IdentificationCertainty,
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
                reverse_name="is_related_to", edge_model=ThingToIdentifcation
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
                        "edge_properties": {"certainty": 1},
                    }
                ],
                "identification_description": "not bad",
                "edge_properties": {"something": "some thing"},
            }
        ],
    )

    assert thing.related_to[0].target[0].type == "RelatedThing"
    assert thing.related_to[0].target[0].edge_properties.certainty == 1


@typing.no_type_check
def test_create_with_generic_reified():
    class Identification[T](ReifiedRelation[T]):
        certainty: int

    class ForwardedIdentification[T, U](ReifiedRelation[T]):
        target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
        other: typing.Annotated[U, RelationConfig(reverse_name="is_other_of")]

    class IdentifiedThing(BaseNode):
        pass

    class OtherIdentifiedThing(BaseNode):
        pass

    class Thing(BaseNode):
        identified_thing: typing.Annotated[
            Identification[
                ForwardedIdentification[IdentifiedThing, OtherIdentifiedThing]
            ],
            RelationConfig("is_identified_thing_of"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Thing(
        type="Thing",
        label="A Thing",
        identified_thing=[
            {
                "target": [
                    {
                        "target": [{"uuid": uuid.uuid4(), "type": "IdentifiedThing"}],
                        "other": [
                            {"uuid": uuid.uuid4(), "type": "OtherIdentifiedThing"}
                        ],
                    }
                ],
                "certainty": 1,
            }
        ],
    )


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


@typing.no_type_check
def test_initialise_model_with_reified_node_in_relation():
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
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Event(
        type="Event",
        label="An Event",
        carried_out_by=[
            {
                "label": "Smith acts as proxy for Jones",
                "type": "WithProxyActor[Identification[test_initialise_model_with_reified_node_in_relation.<locals>.Person]]",
                "target": [
                    {
                        "type": "Identification[test_initialise_model_with_reified_node_in_relation.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                            }
                        ],
                    }
                ],
                "proxy": [
                    {
                        "type": "Identification[test_initialise_model_with_reified_node_in_relation.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                            }
                        ],
                    }
                ],
            },
        ],
    )


@typing.no_type_check
def test_initialise_model_view():
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
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Event.View(
        uuid=uuid.uuid4(),
        type="Event",
        label="An Event",
        created_by="editor",
        created_when=datetime.datetime.now(),
        modified_by="editor",
        modified_when=datetime.datetime.now(),
        carried_out_by=[
            {
                "uuid": uuid.uuid4(),
                "label": "Smith acts as proxy for Jones",
                "type": "WithProxyActor[Identification[test_initialise_model_view.<locals>.Person]]",
                "created_by": "editor",
                "created_when": datetime.datetime.now(),
                "modified_by": "editor",
                "modified_when": datetime.datetime.now(),
                "target": [
                    {
                        "uuid": uuid.uuid4(),
                        "type": "Identification[test_initialise_model_view.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Smith",
                            }
                        ],
                    }
                ],
                "proxy": [
                    {
                        "uuid": uuid.uuid4(),
                        "type": "Identification[test_initialise_model_view.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Jones",
                            }
                        ],
                    }
                ],
            },
        ],
    )


@typing.no_type_check
def test_initialise_model_edit_view():
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
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Event.EditView(
        uuid=uuid.uuid4(),
        type="Event",
        label="An Event",
        created_by="editor",
        created_when=datetime.datetime.now(),
        modified_by="editor",
        modified_when=datetime.datetime.now(),
        carried_out_by=[
            {
                "uuid": uuid.uuid4(),
                "label": "Smith acts as proxy for Jones",
                "type": "WithProxyActor[Identification[test_initialise_model_edit_view.<locals>.Person]]",
                "created_by": "editor",
                "created_when": datetime.datetime.now(),
                "modified_by": "editor",
                "modified_when": datetime.datetime.now(),
                "target": [
                    {
                        "uuid": uuid.uuid4(),
                        "type": "Identification[test_initialise_model_edit_view.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Smith",
                            }
                        ],
                    }
                ],
                "proxy": [
                    {
                        "uuid": uuid.uuid4(),
                        "type": "Identification[test_initialise_model_edit_view.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Jones",
                            }
                        ],
                    }
                ],
            },
        ],
    )


@typing.no_type_check
def test_initialise_model_edit_set():
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
        carried_out_by: typing.Annotated[
            WithProxyActor[Identification[Person]],
            RelationConfig(reverse_name="is_carried_out_by"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    Event.EditSet(
        uuid=uuid.uuid4(),
        type="Event",
        label="An Event",
        created_by="editor",
        created_when=datetime.datetime.now(),
        modified_by="editor",
        modified_when=datetime.datetime.now(),
        carried_out_by=[
            {
                "uuid": uuid.uuid4(),
                "label": "Smith acts as proxy for Jones",
                "type": "WithProxyActor[Identification[test_initialise_model_edit_set.<locals>.Person]]",
                "created_by": "editor",
                "created_when": datetime.datetime.now(),
                "modified_by": "editor",
                "modified_when": datetime.datetime.now(),
                "target": [
                    # Previous version can be posted
                    {
                        "uuid": uuid.uuid4(),
                        "type": "Identification[test_initialise_model_edit_set.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Smith",
                            }
                        ],
                    },
                    # New version without UUID
                    {
                        "type": "Identification[test_initialise_model_edit_set.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Smith Two",
                            }
                        ],
                    },
                ],
                "proxy": [
                    {
                        "uuid": uuid.uuid4(),
                        "type": "Identification[test_initialise_model_edit_set.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Jones",
                            }
                        ],
                    },
                    {
                        "type": "Identification[test_initialise_model_edit_set.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Jones Two",
                            }
                        ],
                    },
                ],
            },
            # And add an extra new Proxy
            {
                "label": "Foo acts as proxy for Bar",
                "type": "WithProxyActor[Identification[test_initialise_model_edit_set.<locals>.Person]]",
                "target": [
                    # Previous version can be posted
                    {
                        "type": "Identification[test_initialise_model_edit_set.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Bar",
                            }
                        ],
                    },
                ],
                "proxy": [
                    {
                        "type": "Identification[test_initialise_model_edit_set.<locals>.Person]",
                        "target": [
                            {
                                "edge_properties": {"certainty": 1},
                                "type": "Person",
                                "uuid": uuid.uuid4(),
                                "label": "Foo",
                            }
                        ],
                    },
                ],
            },
        ],
    )


@typing.no_type_check
def test_initialise_base_model_with_multi_key_field():
    class WithCertainty[T](MultiKeyField[T]):
        certainty: int

    class Thing(BaseNode):
        name: WithCertainty[str]

    ModelManager.initialise_models(_defined_in_test=True)

    Thing(label="A Thing", type="Thing", name={"value": "John", "certainty": 1})


@typing.no_type_check
def test_initialise_view_model_with_multi_key_field():
    """When preparing a view, i.e. from DB, multi-key fields should be collected
    back into a dict"""

    class WithCertainty[T](MultiKeyField[T]):
        certainty: int

    class Thing(BaseNode):
        name: WithCertainty[str]

    ModelManager.initialise_models(_defined_in_test=True)

    t = Thing.View(
        uuid=uuid.uuid4(),
        created_by="editor",
        created_when=datetime.datetime.now(),
        modified_by="editor",
        modified_when=datetime.datetime.now(),
        label="A Thing",
        type="Thing",
        name____value="John",
        name____certainty=1,
    )

    assert not getattr(t, "name____value", None)
    assert not getattr(t, "name____certainty", None)
    assert t.name
    assert t.name.value == "John"
    assert t.name.certainty == 1


@typing.no_type_check
def test_initialise_edit_view_model_with_multi_key_field():
    """When preparing an edit view, i.e. from DB, multi-key fields should be collected
    back into a dict"""

    class WithCertainty[T](MultiKeyField[T]):
        certainty: int

    class Thing(BaseNode):
        name: WithCertainty[str]

    ModelManager.initialise_models(_defined_in_test=True)

    t = Thing.EditView(
        uuid=uuid.uuid4(),
        created_by="editor",
        created_when=datetime.datetime.now(),
        modified_by="editor",
        modified_when=datetime.datetime.now(),
        label="A Thing",
        type="Thing",
        name____value="John",
        name____certainty=1,
    )

    assert not getattr(t, "name____value", None)
    assert not getattr(t, "name____certainty", None)
    assert t.name
    assert t.name.value == "John"
    assert t.name.certainty == 1


def test_labels():
    class Entity(BaseNode):
        pass

    class CanBreathe(HeritableTrait):
        pass

    class Animal(Entity, CanBreathe):
        pass

    class NotThis(NonHeritableTrait):
        pass

    class Dog(Animal, NotThis):
        pass

    class SitsOnLaps(NonHeritableTrait):
        pass

    class ExpensiveDog(Dog, SitsOnLaps):
        pass

    ModelManager.initialise_models(_defined_in_test=True)

    assert ExpensiveDog.labels == {
        "BaseNode",
        "Entity",
        "Animal",
        "CanBreathe",
        "Dog",
        "ExpensiveDog",
        "SitsOnLaps",
    }


def test_labels_on_reified_relation():
    class Certainty(EdgeModel):
        certainty: int

    T = typing.TypeVar("T")

    class Identification(ReifiedRelation[T]):
        target: typing.Annotated[
            T, RelationConfig(reverse_name="is_target_of", edge_model=Certainty)
        ]

    class Person(BaseNode):
        pass

    class Event(BaseNode):
        involves_person: typing.Annotated[
            Identification[Person], RelationConfig(reverse_name="is_involved_in")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    assert Identification[Person].labels == set(["Identification", "ReifiedRelation"])
