from __future__ import annotations

import pytest

from pangloss.models import BaseNode, HeritableTrait, NonHeritableTrait
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_utils import (
    get_concrete_model_types,
    get_direct_instantiations_of_trait,
    get_trait_subclasses,
    model_is_trait,
)


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


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
