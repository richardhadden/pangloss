import asyncio

import pytest
from pydantic import AnyHttpUrl

from pangloss.database import initialise_database_driver
from pangloss.settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "MyTestApp"
    BACKEND_CORS_ORIGINS: list[AnyHttpUrl] = []

    DB_URL: str = "bolt://localhost:7688"
    DB_USER: str = "neo4j"
    DB_PASSWORD: str = "password"
    DB_DATABASE_NAME: str = "neo4j"

    INSTALLED_APPS: list[str] = ["pangloss_core"]
    authjwt_secret_key: str = "SECRET"

    INTERFACE_LANGUAGES: list[str] = ["en"]


settings = Settings()


initialise_database_driver(settings)


@pytest.fixture(scope="session")
def event_loop(request):
    from pangloss.database import Database, close_database_connection
    from pangloss.indexes import _install_index_and_constraints_from_text

    loop = asyncio.get_event_loop_policy().new_event_loop()
    loop.run_until_complete(Database.dangerously_clear_database())
    loop.run_until_complete(_install_index_and_constraints_from_text())
    loop.run_until_complete(Database.create_default_user())
    yield loop
    # loop.run_until_complete(Database.dangerously_clear_database())
    loop.run_until_complete(close_database_connection())
    loop.close()
