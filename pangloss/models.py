from __future__ import annotations

import typing

from pangloss.cypher.create import build_create_node_query_object
from pangloss.database import write_transaction, Transaction
from pangloss.model_config.models_base import (
    RootNode,
    Embedded,
    RelationConfig,
    ReifiedRelation,
    HeritableTrait,
    NonHeritableTrait,
    EdgeModel,
    ReifiedRelationNode,
    MultiKeyField,
    ReferenceViewBase,
)
from pangloss.model_config.model_manager import ModelManager


# This is doing nothing, just making sure the import is being used
# so won't be cleared up by linters
(
    RelationConfig,
    Embedded,
    ReifiedRelation,
    HeritableTrait,
    NonHeritableTrait,
    EdgeModel,
    ReifiedRelationNode,
    MultiKeyField,
)  # type: ignore


class BaseNode(RootNode):
    @classmethod
    def __pydantic_init_subclass__(cls) -> None:
        # Set the `type` field to a literal
        # (type-checking needs to be overridden as this can't be dynamic!)
        cls.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore

        # Set class as abstract if it has __abstract__ set to True on its
        # own class dict (i.e. not inherited)
        cls.__abstract__ = cls.__dict__.get("__abstract__", False)

        # Register the model with ModelManager
        ModelManager.register_model(cls)

    @write_transaction
    async def create(self, tx: Transaction) -> ReferenceViewBase:
        query_object = build_create_node_query_object(self, start_node=True)
        query = typing.cast(typing.LiteralString, query_object.to_query_string())
        result = await tx.run(query, query_object.query_params)
        record = await result.value()
        print(record)
        return self.ReferenceView(**record[0])
