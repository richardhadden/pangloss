import pytest_asyncio
from pydantic import AnyHttpUrl

from pangloss.neo4j.database import initialise_database_driver
from pangloss.settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "MyTestApp"
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    DB_URL: str = "bolt://localhost:7688"
    DB_USER: str = "neo4j"
    DB_PASSWORD: str = "password"
    DB_DATABASE_NAME: str = "neo4j"

    INSTALLED_APPS: list[str] = ["pangloss_core"]
    AUTHJWT_SECRET_KEY: str = "SECRET"

    INTERFACE_LANGUAGES: list[str] = ["en"]

    ENTITY_BASE_URL: AnyHttpUrl = AnyHttpUrl("http://pangloss_test.com")


settings = Settings()


initialise_database_driver(settings)


@pytest_asyncio.fixture(loop_scope="module", autouse=True)
def database_setup(event_loop):
    print("running")
    from pangloss.indexes import _install_index_and_constraints_from_text
    from pangloss.neo4j.database import (
        DRIVER,
        Database,
        close_database_connection,
        initialise_database_driver,
    )

    if not DRIVER:
        initialise_database_driver(settings)

    event_loop.run_until_complete(Database.dangerously_clear_database())
    event_loop.run_until_complete(_install_index_and_constraints_from_text())
    event_loop.run_until_complete(Database.create_default_user())
    yield
    event_loop.run_until_complete(close_database_connection())
