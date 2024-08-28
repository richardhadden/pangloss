from __future__ import annotations

import pytest

import datetime
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


@typing.no_type_check
def test_initialisation_of_view_model_with_basic_rel():
    class Thing(BaseNode):
        name: str
        related_to: typing.Annotated[
            RelatedThing, RelationConfig(reverse_name="has_relation_to")
        ]

    class RelatedThing(BaseNode):
        name: str

    ModelManager.initialise_models(_defined_in_test=True)

    Thing(
        label="Thing",
        name="Thing",
        related_to=[
            {"type": "RelatedThing", "uuid": uuid.uuid4(), "label": "A Related Thing"}
        ],
    )

    Thing.View(
        type="Thing",
        uuid=uuid.uuid4(),
        created_by="User1",
        created_when=datetime.datetime.now(),
        modified_by="User1",
        modified_when=datetime.datetime.now(),
        label="Thing1",
        name="Thing",
        related_to=[
            {"type": "RelatedThing", "uuid": uuid.uuid4(), "label": "A Related Thing"}
        ],
    )

    assert "has_relation_to" in RelatedThing.View.model_fields.keys()
    # assert RelatedThing.View.model_fields["has_relation_to"] == {}

    rt = RelatedThing.View(
        type="RelatedThing",
        uuid=uuid.uuid4(),
        created_by="User1",
        created_when=datetime.datetime.now(),
        modified_by="User1",
        modified_when=datetime.datetime.now(),
        label="RelatedThing1",
        name="RelatedThing1",
        has_relation_to=[
            Thing.ReferenceView(type="Thing", label="Thing", uuid=uuid.uuid4())
        ],
    )

    assert rt.has_relation_to

    assert rt.has_relation_to[0].label == "Thing"


@typing.no_type_check
def test_initialisation_of_view_model_with_reified_rel():
    class Certainty(RelationPropertiesModel):
        certainty: int

    class Person(BaseNode):
        pass

    class RepresentedByProxy[T](ReifiedRelation[T]):
        proxy: typing.Annotated[
            Identification[Person], RelationConfig(reverse_name="acts_as_proxy_in")
        ]

    T = typing.TypeVar("T")

    class Identification(ReifiedRelation[T]):
        target: typing.Annotated[
            T, RelationConfig(reverse_name="is_target_of", relation_model=Certainty)
        ]

    class Action(BaseNode):
        carried_out_by_person: typing.Annotated[
            RepresentedByProxy[Identification[Person]],
            RelationConfig("carried_out_action"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    p1_uuid = uuid.uuid4()
    p2_uuid = uuid.uuid4()

    action = Action(
        type="Action",
        label="Action1",
        carried_out_by_person=[
            {
                "target": [
                    {
                        "target": [
                            {
                                "type": "Person",
                                "uuid": p1_uuid,
                                "relation_properties": {"certainty": 1},
                            }
                        ]
                    }
                ],
                "proxy": [
                    {
                        "target": [
                            {
                                "type": "Person",
                                "uuid": p2_uuid,
                                "relation_properties": {"certainty": 2},
                            }
                        ]
                    }
                ],
            },
        ],
    )

    assert action.carried_out_by_person[0].target[0].target[0].uuid == p1_uuid
    assert (
        action.carried_out_by_person[0]
        .target[0]
        .target[0]
        .relation_properties.certainty
        == 1
    )

    assert action.carried_out_by_person[0].proxy[0].target[0].uuid == p2_uuid
    assert (
        action.carried_out_by_person[0].proxy[0].target[0].relation_properties.certainty
        == 2
    )

    # TODO: test reverse relation initialisation on Person.View
    assert "carried_out_action" in Person.View.model_fields.keys()
    assert "acts_as_proxy_in" in Person.View.model_fields.keys()

    a = Person.incoming_relation_definitions["carried_out_action"].pop()

    keys = a.source_concrete_type.model_fields.keys()

    p = Person.View(
        type="Person",
        label="Person1",
        uuid=uuid.uuid4(),
        created_by="User1",
        created_when=datetime.datetime.now(),
        modified_by="User1",
        modified_when=datetime.datetime.now(),
        carried_out_action=[
            {
                "type": "Identification",
                "uuid": uuid.uuid4(),
                "is_target_of": {
                    "relation_properties": {"certainty": 1},
                    "type": "RepresentedByProxy",
                    "uuid": uuid.uuid4(),
                    "is_target_of": {
                        "type": "Action",
                        "label": "Action1",
                        "uuid": uuid.uuid4(),
                        #
                    },
                    "proxy": [
                        {
                            "target": [
                                {
                                    "type": "Person",
                                    "uuid": p2_uuid,
                                    "relation_properties": {"certainty": 2},
                                }
                            ]
                        }
                    ],
                },
            }
        ],
    )

    assert p.carried_out_action[0].uuid
    assert p.carried_out_action[0].is_target_of.uuid

    Person.View(
        type="Person",
        label="Person1",
        uuid=uuid.uuid4(),
        created_by="User1",
        created_when=datetime.datetime.now(),
        modified_by="User1",
        modified_when=datetime.datetime.now(),
        acts_as_proxy_in=[
            {
                "reified_relation_uuid": uuid.uuid4(),
                "reified_relation_data": {
                    "type": "Action",
                    "label": "Action1",
                    "uuid": uuid.uuid4(),
                    "carried_out_by_person": [
                        {
                            "type": "RepresentedByProxy",
                            "target": [
                                {
                                    "type": "Identification",
                                    "target": [
                                        {
                                            "type": "Person",
                                            "uuid": p1_uuid,
                                            "relation_properties": {"certainty": 1},
                                        }
                                    ],
                                }
                            ],
                            "proxy": [
                                {
                                    "type": "Identification",
                                    "target": [
                                        {
                                            "type": "Person",
                                            "uuid": p2_uuid,
                                            "relation_properties": {"certainty": 2},
                                        }
                                    ],
                                }
                            ],
                        },
                    ],
                },
            }
        ],
    )
