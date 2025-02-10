import typing

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.models_base import ReifiedRelation, RootNode


def set_type_to_literal_on_base_model(cls: type["RootNode"] | type["ReifiedRelation"]):
    cls.__annotations__["type"] = typing.Literal[cls.__name__]
    cls.type = cls.__name__
