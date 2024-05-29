from pangloss.model_config.models_base import (
    RootNode,
    Embedded,
    RelationConfig,
    ReifiedRelation,
    HeritableTrait,
    NonHeritableTrait,
)
from pangloss.model_config.model_manager import ModelManager

import typing

# This is doing nothing, just making sure the import is being used
# so won't be cleared up by linters
(RelationConfig, Embedded, ReifiedRelation, HeritableTrait, NonHeritableTrait)  # type: ignore


class BaseNode(RootNode):
    @classmethod
    def __pydantic_init_subclass__(cls) -> None:
        # Set the `type` field to a literal
        # (type-checking needs to be overridden as this can't be dynamic!)
        cls.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore

        # Set class as abstract if it has __abstract__ set to
        cls.__abstract__ = cls.__dict__.get("__abstract__", False)

        # Register the model with ModelManager
        ModelManager.register_model(cls)
