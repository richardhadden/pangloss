from __future__ import annotations

from contextlib import contextmanager
import time
import typing
import uuid

from pangloss.cypher.create import build_create_node_query_object
from pangloss.cypher.read import build_view_read_query
from pangloss.cypher.update import build_update_node_query_object
from pangloss.database import write_transaction, Transaction, read_transaction
from pangloss.exceptions import PanglossNotFoundError
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


@contextmanager
def time_query(label: str = "Query time"):
    start_time = time.perf_counter()
    yield
    print(f"{label}:", time.perf_counter() - start_time)


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

    @classmethod
    @read_transaction
    async def get_view(cls, tx: Transaction, uuid: uuid.UUID | str):
        query, params = build_view_read_query(cls, uuid=uuid)

        with open("get_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(params)}")

        with time_query(f"Get View query time: {cls.__name__}"):
            result = await tx.run(query, params)
            record = await result.value()
        print(record)
        if len(record) == 0:
            raise PanglossNotFoundError(f'<{cls.__name__} uid="{str(uuid)}"> not found')

        return cls.HeadView(**record[0])

    @classmethod
    @read_transaction
    async def get_edit_view(cls, tx: Transaction, uuid: uuid.UUID | str):
        query, params = build_view_read_query(cls, uuid=uuid)
        with open("get_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(params)}")
        result = await tx.run(query, params)
        record = await result.value()
        # print(">>", record)
        if len(record) == 0:
            raise PanglossNotFoundError(f'<{cls.__name__} uid="{str(uuid)}"> not found')

        return cls.EditView(**record[0])

    @write_transaction
    async def create(self, tx: Transaction) -> ReferenceViewBase:
        query_object, *_ = build_create_node_query_object(self, head_node=True)
        query = typing.cast(typing.LiteralString, query_object.to_query_string())
        with open("create_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(query_object.query_params)}")

        with time_query("Create query time"):
            result = await tx.run(query, query_object.query_params)
            record = await result.value()

        return self.ReferenceView(**record[0])

    @classmethod
    @write_transaction
    async def _update_method(cls, tx: Transaction, instance) -> bool:
        query_object, _, should_update = await build_update_node_query_object(
            instance, head_node=True
        )
        if should_update:
            query = typing.cast(typing.LiteralString, query_object.to_query_string())

            with open("update_query_dump.cypher", "w") as f:
                f.write(f"{query}\n\n//{str(query_object.query_params)}")

            with time_query("Update query time"):
                result = await tx.run(query, query_object.query_params)
                value = await result.value()

            if value:
                return value[0]
            else:
                return False
        else:
            return True
