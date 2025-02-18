import pytest

from pangloss_new.exceptions import PanglossConfigError
from pangloss_new.model_config.model_manager import ModelManager
from pangloss_new.models import BaseMeta, BaseNode


def test_base_meta_not_inherited_by_class_not_called_meta_raises_error():
    with pytest.raises(PanglossConfigError):

        class Thing(BaseNode):
            class SomeShit(BaseMeta):
                abstract = True

        ModelManager.initialise_models()


def test_base_meta_inherits_except_abstract():
    class Thing(BaseNode):
        class Meta(BaseMeta):
            abstract = True
            create = False

    class SubThing(Thing):
        pass

    class SubSubThing(SubThing):
        class Meta(BaseMeta):
            abstract = True
            delete = False

    class Other(BaseNode):
        class Meta(BaseMeta):
            view: bool = False

    ModelManager.initialise_models()

    assert Thing.Meta.abstract
    assert not Thing.Meta.create
    assert Thing.Meta.edit
    assert Thing.Meta.delete

    assert not SubThing.Meta.abstract
    assert not SubThing.Meta.create
    assert SubThing.Meta.edit
    assert SubThing.Meta.delete

    assert SubSubThing.Meta.abstract
    assert not SubSubThing.Meta.create
    assert SubSubThing.Meta.edit
    assert not SubSubThing.Meta.delete

    assert not Other.Meta.view

    assert not Other.Meta.view
