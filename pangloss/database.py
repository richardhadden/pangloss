from __future__ import annotations

import functools
import uuid
from typing import (
    Awaitable,
    Callable,
    Concatenate,
)

import neo4j
from rich import print

from pangloss.background_tasks import background_task_close

# Define a transaction type, for short
Transaction = neo4j.AsyncManagedTransaction


DRIVER: neo4j.AsyncDriver

uri: str
auth: tuple[str, str]
database: str


def initialise_database_driver(SETTINGS):
    global DRIVER, uri, auth, database
    # from pangloss_core.settings import SETTINGS

    uri = SETTINGS.DB_URL  # "bolt://localhost:7687"
    auth = (SETTINGS.DB_USER, SETTINGS.DB_PASSWORD)
    # auth = ("neo4j", "password")
    database = SETTINGS.DB_DATABASE_NAME
    # database = "neo4j"
    DRIVER = neo4j.AsyncGraphDatabase.driver(
        SETTINGS.DB_URL,
        auth=(SETTINGS.DB_USER, SETTINGS.DB_PASSWORD),
        keep_alive=True,
    )


@background_task_close
async def close_database_connection():
    print("[yellow bold]Closing Database connection...[/yellow bold]")
    try:
        await DRIVER.close()
    except Exception as e:
        print("[red bold]Error closing database:[/red bold]", e)
    else:
        print("[green bold]Database connection closed[/green bold]")


def read_transaction[ModelType, ReturnType, **Params](
    func: Callable[
        Concatenate[ModelType, neo4j.AsyncManagedTransaction, Params],
        Awaitable[ReturnType],
    ],
) -> Callable[Concatenate[ModelType, Params], Awaitable[ReturnType]]:
    async def wrapper(
        cls: ModelType, *args: Params.args, **kwargs: Params.kwargs
    ) -> ReturnType:
        # async with neo4j.AsyncGraphDatabase.driver(uri, auth=auth) as driver:
        async with DRIVER.session(database=database) as session:
            bound_func = functools.partial(func, cls)
            records = await session.execute_read(bound_func, *args, **kwargs)
            return records

    return wrapper


def write_transaction[ModelType, ReturnType, **Params](
    func: Callable[
        Concatenate[ModelType, neo4j.AsyncManagedTransaction, Params],
        Awaitable[ReturnType],
    ],
) -> Callable[Concatenate[ModelType, Params], Awaitable[ReturnType]]:
    async def wrapper(
        cls: ModelType, *args: Params.args, **kwargs: Params.kwargs
    ) -> ReturnType:
        # async with neo4j.AsyncGraphDatabase.driver(uri, auth=auth) as driver:
        async with DRIVER.session(database=database) as session:
            bound_func = functools.partial(func, cls)
            records = await session.execute_write(bound_func, *args, **kwargs)

            return records

    return wrapper


class Database:
    @classmethod
    @read_transaction
    async def get_item(
        cls,
        tx: Transaction,
        uid: uuid.UUID,
    ) -> neo4j.Record | None:
        result = await tx.run("MATCH (n {uid: $uid}) RETURN n", uid=str(uid))
        item = await result.single()
        summary = await result.consume()
        print(item)
        print(summary)
        return item

    @classmethod
    @write_transaction
    async def write_indexes(cls, tx: Transaction) -> None:
        result = await tx.run(
            """CREATE CONSTRAINT BaseNodeUidUnique IF NOT EXISTS FOR (n:BaseNode) REQUIRE n.uuid IS UNIQUE"""
        )
        await result.consume()
        result = await tx.run(
            """CREATE CONSTRAINT PGUserNameIndex IF NOT EXISTS FOR (n:PGUser) REQUIRE n.username IS UNIQUE"""
        )
        await result.consume()

    @classmethod
    @write_transaction
    async def dangerously_clear_database(cls, tx: Transaction) -> None:
        result = await tx.run("""MATCH (n) DETACH DELETE n
                              MERGE (:PGInternal:PGCore:PGUser {username: "DefaultUser"})

                              """)
        await result.consume()

    @classmethod
    @write_transaction
    async def create_default_user(cls, tx: Transaction) -> None:
        result = await tx.run(
            """MERGE (:PGInternal:PGCore:PGUser {username: "DefaultUser"})"""
        )
        await result.consume()

    @classmethod
    @write_transaction
    async def _cypher_write(cls, tx: Transaction, query: str, params: dict = {}):
        result = await tx.run(
            query,  # type: ignore
            **params,
        )
        records = await result.values()
        return records
