import pytest

from pangloss.model_config.model_manager import ModelManager
from pangloss.models import BaseNode


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
