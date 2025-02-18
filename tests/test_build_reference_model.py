import typing

from pydantic import AnyHttpUrl
from ulid import ULID

from pangloss_new.model_config.model_manager import ModelManager
from pangloss_new.model_config.models_base import ReferenceSetBase, ReferenceViewBase
from pangloss_new.models import BaseNode
from pangloss_new.utils import gen_ulid, url


def test_reference_set_on_model():
    class Entity(BaseNode):
        name: str

    class Person(Entity):
        pass

    ModelManager.initialise_models()

    assert Entity.ReferenceSet
    assert issubclass(Entity.ReferenceSet, ReferenceSetBase)
    assert Entity.ReferenceSet.__pg_base_class__ is Entity
    assert Entity.ReferenceSet.__pg_field_definitions__
    assert (
        Entity.ReferenceSet.model_fields["type"].annotation == typing.Literal["Entity"]
    )
    assert Entity.ReferenceSet.model_fields["type"].default == "Entity"
    Entity.ReferenceSet.model_fields.keys()

    e = Entity.ReferenceSet(id=gen_ulid(), type="Entity")
    assert isinstance(e.id, ULID)
    assert e.type == "Entity"

    e = Entity.ReferenceSet(id=url("http://www.madeup.com/entity/1"), type="Entity")
    assert isinstance(e.id, AnyHttpUrl)
    assert e.type == "Entity"

    assert Person.ReferenceSet
    assert issubclass(Person.ReferenceSet, ReferenceSetBase)


def test_reference_view_on_model():
    class Entity(BaseNode):
        name: str

    class Person(Entity):
        pass

    ModelManager.initialise_models()

    assert Entity.ReferenceView
    assert issubclass(Entity.ReferenceView, ReferenceViewBase)
    assert Entity.ReferenceView.__pg_base_class__ is Entity
    assert Entity.ReferenceView.__pg_field_definitions__
    assert (
        Entity.ReferenceView.model_fields["type"].annotation == typing.Literal["Entity"]
    )
    assert Entity.ReferenceView.model_fields["type"].default == "Entity"
    Entity.ReferenceView.model_fields.keys()

    e = Entity.ReferenceView(id=gen_ulid(), type="Entity", label="An Entity")
    assert isinstance(e.id, ULID)
    assert e.type == "Entity"

    assert Person.ReferenceView
    assert issubclass(Person.ReferenceView, ReferenceViewBase)
