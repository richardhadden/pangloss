import time
import typing
from contextlib import contextmanager

from pydantic import BaseModel
from ulid import ULID

from pangloss.exceptions import PanglossNotFoundError
from pangloss.model_config.model_base_mixins import _StandardModel
from pangloss.neo4j.create import build_create_query_object
from pangloss.neo4j.database import Transaction, database
from pangloss.neo4j.list import build_get_list_query
from pangloss.neo4j.read import build_edit_view_query, build_view_read_query

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import (
        CreateBase,
        EditHeadViewBase,
        HeadViewBase,
        ReferenceViewBase,
        RootNode,
    )


@contextmanager
def time_query(label: str = "Query time"):
    start_time = time.perf_counter()
    yield
    elapsed_time = time.perf_counter() - start_time
    print(f"{label}:", elapsed_time)
    return elapsed_time


class SearchResultObject[T](BaseModel, _StandardModel):
    count: int
    page: int
    total_pages: int
    page_size: int
    results: list[T]


class DatabaseQueryMixin:
    @database.write_transaction
    async def create_method(
        self,
        tx: Transaction,
        current_username: str | None = None,
        use_deferred_query: bool = False,
        return_edit_view: bool = True,
    ) -> "ReferenceViewBase":
        print("=============")

        self = typing.cast("CreateBase", self)

        with time_query(f"Building create query time for {self.type}"):
            query_object = build_create_query_object(
                instance=self, current_username=current_username
            )
        query = typing.cast(typing.LiteralString, query_object.to_query_string())

        with open("create_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(query_object.params)}")

        with time_query(f"Create query time for {self.type}"):
            result = await tx.run(
                query, typing.cast(dict[str, typing.Any], query_object.params)
            )
            record = await result.value()

        if use_deferred_query:
            pass

        if query_object.deferred_query.params:
            deferred_query = typing.cast(
                typing.LiteralString, query_object.deferred_query.to_query_string()
            )
            with open("deferred_create_query_dump.cypher", "w") as f:
                f.write(
                    f"{deferred_query}\n\n//{str(query_object.deferred_query.params)}"
                )

            with time_query(f"Deferred create query time for {self.type}"):
                deferred_query = await tx.run(
                    deferred_query,
                    typing.cast(
                        dict[str, typing.Any], query_object.deferred_query.params
                    ),
                )

        response = typing.cast("RootNode", self.__pg_base_class__).ReferenceView(
            **record[0]
        )

        if not return_edit_view:
            return response
        print("=============")
        with time_query(f"Building read query time for {self.type}"):
            query, query_params = build_edit_view_query(
                model=self.__pg_base_class__, id=str(response.id)
            )

        with open("get_edit_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(query_params)}")

        with time_query(f"Read query time for {self.type}"):
            result = await tx.run(
                query, typing.cast(dict[str, typing.Any], query_params)
            )
            record = await result.value()
            if record:
                result = self.__pg_base_class__.EditHeadView(**record[0])
            else:
                raise PanglossNotFoundError(f"Object <{self.type} id='{id}'> not found")

        return result

    @classmethod
    @database.read_transaction
    async def get_view(cls, tx: Transaction, id: ULID | str) -> "HeadViewBase":
        print("=============")

        cls = typing.cast(type["RootNode"], cls)
        with time_query(f"Building read query time for {cls.type}"):
            query, query_params = build_view_read_query(model=cls, id=str(id))

        with open("get_view_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(query_params)}")

        with time_query(f"View read query time for {cls.type}"):
            result = await tx.run(
                query, typing.cast(dict[str, typing.Any], query_params)
            )
            record = await result.value()
            if record:
                result = cls.HeadView(**record[0])

            else:
                raise PanglossNotFoundError(f"Object <{cls.type} id='{id}'> not found")

        return result

    @classmethod
    @database.read_transaction
    async def get_edit_view(cls, tx: Transaction, id: ULID | str) -> "EditHeadViewBase":
        print("=============")
        cls = typing.cast(type["RootNode"], cls)
        with time_query(f"Building read query time for {cls.type}"):
            query, query_params = build_edit_view_query(model=cls, id=str(id))

        with open("get_edit_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(query_params)}")

        with time_query(f"EditView read query time for {cls.type}"):
            result = await tx.run(
                query, typing.cast(dict[str, typing.Any], query_params)
            )
            record = await result.value()
            if record:
                result = cls.EditHeadView(**record[0])
            else:
                raise PanglossNotFoundError(f"Object <{cls.type} id='{id}'> not found")

        return result

    @classmethod
    @database.read_transaction
    async def get_list(
        cls,
        tx: Transaction,
        q: typing.Optional[str] = None,
        page: int = 1,
        page_size: int = 10,
        deep_search: bool = False,
    ) -> SearchResultObject["ReferenceViewBase"]:
        print("=============")
        cls = typing.cast(type["RootNode"], cls)
        with time_query(f"Building search query time for {cls.type}"):
            query, query_params = build_get_list_query(
                model=cls, q=q, page=page, page_size=page_size, deep_search=deep_search
            )
        with open("get_list_query_dump.cypher", "w") as f:
            f.write(f"{query}\n\n//{str(query_params)}")

        with time_query(f"List read query time for {cls.type} with query '{q}'"):
            result = await tx.run(
                query, typing.cast(dict[str, typing.Any], query_params)
            )
            records = await result.value()
            return_object = SearchResultObject[cls.ReferenceView](**records[0])

            return return_object
