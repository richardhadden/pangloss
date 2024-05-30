import pytest

import typing

from pangloss.exceptions import PanglossConfigError
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_utils import is_subclass_of_heritable_trait
from pangloss.model_config.model_setup_functions import (
    initialise_reference_set_on_base_models,
    initialise_reference_view_on_base_models,
)
from pangloss.model_config.models_base import ReferenceSetBase, ReferenceViewBase
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


def test_initialise_relation_field_on_model():
    class RelatedThing(BaseNode):
        pass

    class OtherRelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        related_to: typing.Annotated[
            RelatedThing | OtherRelatedThing,
            RelationConfig(reverse_name="is_related_to"),
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    # assert Thing.model_fields["related_to"].annotation


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
