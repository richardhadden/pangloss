from typing import Annotated

from annotated_types import Gt

from pangloss_new.model_config.model_manager import ModelManager
from pangloss_new.models import BaseNode, RelationConfig


def test_build_creation_model():
    class Cat(BaseNode):
        pass

    class Person(BaseNode):
        age: Annotated[int, Gt(1)]
        owns_cat: Annotated[Cat, RelationConfig(reverse_name="is_owned_by")]

    ModelManager.initialise_models()

    assert Person.Create

    mr_fluffy = Cat(label="Mister Fluffy")

    john_smith = Person(label="John Smith", age="2", owns_cat=[mr_fluffy])
