import pytest

from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_utils import is_subclass_of_heritable_trait
from pangloss.models import BaseNode, HeritableTrait


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
