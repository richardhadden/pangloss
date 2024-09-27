import typing
import uuid

import pydantic
import pytest

from pangloss.models import BaseNode, RelationConfig, MultiKeyField
from pangloss.model_config.model_manager import ModelManager
from pangloss.cypher.utils import get_properties_as_writeable_dict


@pytest.fixture(scope="function", autouse=True)
def reset_model_manager():
    ModelManager._reset()


@typing.no_type_check
def test_get_properties_as_writeable_dict():
    class WithCertainty[T](MultiKeyField[T]):
        certainty: int

    class RelatedThing(BaseNode):
        pass

    class Thing(BaseNode):
        name: str
        age: int
        some_set: set[str]
        some_tuple: tuple[str, str]
        website: pydantic.AnyHttpUrl
        nickname: WithCertainty[str]
        related_to: typing.Annotated[
            RelatedThing, RelationConfig(reverse_name="is_related_to")
        ]

    ModelManager.initialise_models(_defined_in_test=True)

    thing = Thing(
        type="Thing",
        label="A Thing",
        name="Thingy",
        age=1,
        some_set={"one", "two"},
        some_tuple=("three", "four"),
        website="http://something.com/",
        related_to=[
            {"type": "RelatedThing", "uuid": uuid.uuid4(), "label": "A Related Thing"}
        ],
        nickname={"value": "Thang", "certainty": 1},
    )

    props = get_properties_as_writeable_dict(thing)
    assert isinstance(props, dict)
    assert props["type"] == "Thing"

    assert props["label"] == "A Thing"
    assert props["name"] == "Thingy"
    assert props["age"] == 1
    assert set(props["some_set"]) == set(["two", "one"])
    assert props["some_tuple"] == ["three", "four"]
    assert props["website"] == "http://something.com/"
    assert props["nickname____value"] == "Thang"
    assert props["nickname____certainty"] == 1

    assert "related_to" not in props
