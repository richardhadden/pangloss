from __future__ import annotations

import typing

import pytest

from pangloss.model_config.models_base import EdgeModel
from pangloss.models import (
    BaseNode,
    HeritableTrait,
    NonHeritableTrait,
    ReifiedRelation,
    RelationConfig,
)
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_utils import (
    create_reference_set_model_with_property_model,
    get_concrete_model_types,
    get_direct_instantiations_of_trait,
    get_trait_subclasses,
    model_is_trait,
    generic_get_subclasses,
    get_subclasses_of_reified_relations,
    get_non_heritable_traits_as_direct_ancestors,
    get_non_heritable_traits_as_indirect_ancestors,
)


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


def test_generic_get_subclasses():
    class Thing:
        pass

    class SubThing(Thing):
        pass

    class SubSubThing(SubThing):
        pass

    assert generic_get_subclasses(Thing) == set([SubThing, SubSubThing])


def test_model_is_trait():
    class Relatable(HeritableTrait):
        pass

    class Thing(BaseNode, Relatable):
        pass

    assert model_is_trait(Relatable)
    assert not model_is_trait(Thing)


def test_get_direct_instantiations_of_trait():
    class Relatable(HeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class Thong(BaseNode, Relatable):
        pass

    class SubThong(Thong):
        pass

    assert get_direct_instantiations_of_trait(Relatable) == set([Thing, Thong])


def test_get_direct_instantiations_of_trait_following_subclasses():
    class Relatable(HeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class Thong(BaseNode, VeryRelatable):
        pass

    class SubThong(Thong):
        pass

    assert get_direct_instantiations_of_trait(
        Relatable, follow_trait_subclasses=True
    ) == set([Thing, Thong])


def test_get_trait_subclasses():
    class Relatable(HeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class VeryVeryRelatable(VeryRelatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class OtherThing(BaseNode, VeryRelatable):
        pass

    class OtherOtherThing(BaseNode, VeryVeryRelatable):
        pass

    assert get_trait_subclasses(Relatable) == set(
        [Relatable, VeryRelatable, VeryVeryRelatable]
    )


def test_get_subclasses_of_reified_relations():
    class Person(BaseNode):
        pass

    class Identification[T](ReifiedRelation[T]):
        pass

    class SubIdentification[T](Identification[T]):
        pass

    class SubSubIdentification[T](Identification[T]):
        pass

    class PersonIdentification(Identification[Person]):
        target: typing.Annotated[
            Person, RelationConfig(reverse_name="is_target_of_identification")
        ]

    class SpecialPersonIdentification(PersonIdentification):
        pass

    class ReallySpecialPersonIdentification(SpecialPersonIdentification):
        pass

    assert get_subclasses_of_reified_relations(Identification[Person]) == {
        Identification[Person],
        SubIdentification[Person],
        SubSubIdentification[Person],
    }
    assert get_subclasses_of_reified_relations(PersonIdentification) == {
        PersonIdentification,
        SpecialPersonIdentification,
        ReallySpecialPersonIdentification,
    }


def test_get_concrete_model_types_include_subclasses():
    class Thing(BaseNode):
        pass

    class SubThing(Thing):
        pass

    class SubSubThing(SubThing):
        pass

    assert get_concrete_model_types(
        Thing, include_abstract=True, include_subclasses=True
    ) == set([Thing, SubThing, SubSubThing])


def test_get_concrete_model_types_do_not_include_abstract():
    class Thing(BaseNode):
        pass

    class SubThing(Thing):
        __abstract__ = True

    class SubSubThing(SubThing):
        pass

    assert get_concrete_model_types(
        Thing, include_abstract=False, include_subclasses=True
    ) == set([Thing, SubSubThing])


def test_get_concrete_model_types_from_union():
    class Thing(BaseNode):
        pass

    class SubThing(Thing):
        __abstract__ = True

    class SubSubThing(SubThing):
        pass

    class Thong(BaseNode):
        pass

    class SubThong(Thong):
        __abstract__ = True

    class SubSubThong(SubThong):
        pass

    assert get_concrete_model_types(
        Thing | Thong, include_abstract=False, include_subclasses=True
    ) == set([Thing, SubSubThing, Thong, SubSubThong])


def test_get_concrete_model_types_from_heritable_trait():
    class Relatable(HeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class SubThing(Thing):
        pass

    class Thong(BaseNode, Relatable):
        pass

    assert get_concrete_model_types(
        Relatable, include_abstract=False, include_subclasses=True
    ) == set([Thing, SubThing, Thong])


def test_get_concrete_model_types_from_heritable_trait_subclasses():
    class Relatable(HeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class SubThing(Thing):
        pass

    class Thong(BaseNode, VeryRelatable):
        pass

    assert get_concrete_model_types(
        Relatable,
        include_abstract=False,
        include_subclasses=True,
        follow_trait_subclasses=True,
    ) == set([Thing, SubThing, Thong])


def test_get_concrete_model_types_for_nonheritable_traits():
    class Relatable(NonHeritableTrait):
        pass

    class VeryRelatable(Relatable):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class SubThing(Thing):
        pass

    class Thong(BaseNode, VeryRelatable):
        pass

    class SubThong(Thong):
        pass

    assert get_concrete_model_types(Relatable, follow_trait_subclasses=True) == set(
        [Thing, Thong]
    )


def test_get_concrete_model_types_for_reified_relations():
    class Person(BaseNode):
        pass

    class ActsOnBehalfOf[T](ReifiedRelation[T]):
        pass

    class Identification[T](ReifiedRelation[T]):
        pass

    class SubIdentification[T](Identification[T]):
        pass

    class SubSubIdentification[T](Identification[T]):
        pass

    class PersonIdentification(Identification[Person]):
        pass

    class SpecialPersonIdentification(PersonIdentification):
        pass

    class ReallySpecialPersonIdentification(SpecialPersonIdentification):
        pass

    assert get_concrete_model_types(Identification[Person]) == {
        Identification[Person],
        SubIdentification[Person],
        SubSubIdentification[Person],
    }
    assert get_concrete_model_types(PersonIdentification) == {
        PersonIdentification,
        SpecialPersonIdentification,
        ReallySpecialPersonIdentification,
    }

    assert get_concrete_model_types(
        Identification[Person] | ActsOnBehalfOf[Identification[Person]]
    ) == {
        Identification[Person],
        SubIdentification[Person],
        SubSubIdentification[Person],
        ActsOnBehalfOf[Identification[Person]],
    }


def test_get_non_heritable_traits_as_direct_ancestors():
    class Relatable(NonHeritableTrait):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class SubThing(Thing):
        pass

    assert get_non_heritable_traits_as_direct_ancestors(Thing) == set([Relatable])
    assert get_non_heritable_traits_as_direct_ancestors(SubThing) == set()


def test_get_non_heritable_traits_as_indirect_ancestors():
    class Relatable(NonHeritableTrait):
        pass

    class Thing(BaseNode, Relatable):
        pass

    class SubThing(Thing):
        pass

    assert get_non_heritable_traits_as_indirect_ancestors(Thing) == set()
    assert get_non_heritable_traits_as_indirect_ancestors(SubThing) == set([Relatable])


def test_create_reference_set_with_relation_property_model():
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

    reference_set_model = create_reference_set_model_with_property_model(
        Thing, RelatedThing, ThingToRelatedThingPropertiesModel, "related_to"
    )

    assert (
        reference_set_model.__name__ == "Thing__related_to__RelatedThing__ReferenceSet"
    )
    assert (
        reference_set_model.model_fields["type"].annotation
        == typing.Literal["RelatedThing"]
    )
    assert reference_set_model.model_fields["edge_properties"]
    assert (
        reference_set_model.model_fields["edge_properties"].annotation
        == ThingToRelatedThingPropertiesModel
    )
