import time
import typing
from contextlib import contextmanager

from pangloss.neo4j.create_new import build_create_query_object
from pangloss.neo4j.database import Transaction, write_transaction

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import (
        CreateBase,
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


class DatabaseQueryMixin:
    @write_transaction
    async def create_method(
        self,
        tx: Transaction,
        current_username: str | None = None,
        use_deferred_query: bool = False,
    ) -> "ReferenceViewBase":
        print("=============")

        self = typing.cast("CreateBase", self)

        with time_query(f"Building query time for {self.type}"):
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

        return typing.cast("RootNode", self.__pg_base_class__).ReferenceView(
            **record[0]
        )
