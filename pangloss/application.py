import asyncio
import contextlib
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from pangloss.database import initialise_database_driver
from pangloss.settings import BaseSettings
from pangloss.users import setup_user_routes

logger = logging.getLogger("uvicorn.info")
RunningBackgroundTasks = []


def get_application(settings: BaseSettings):
    DEVELOPMENT_MODE = "--reload" in sys.argv  # Dumb hack!

    from pangloss.api import setup_api_routes
    from pangloss.background_tasks import (
        BackgroundTaskCloseRegistry,
        BackgroundTaskRegistry,
    )
    from pangloss.model_config.model_manager import ModelManager

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        print("RUNNING LIFESPAN")
        # Load the ML model
        for task in BackgroundTaskRegistry:
            if not DEVELOPMENT_MODE or task["run_in_dev"]:
                running_task = asyncio.create_task(task["function"]())  # type: ignore

                RunningBackgroundTasks.append(running_task)
            else:
                logger.warning(
                    f"Skipping background task '{task["name"]}' for development mode"
                )
        yield

        for task in BackgroundTaskCloseRegistry:
            await task()

        logging.info("Closing background tasks...")
        for task in RunningBackgroundTasks:
            task.cancel()

        logging.info("Background tasks closed")

    for installed_app in settings.INSTALLED_APPS:
        __import__(installed_app)

        __import__(f"{installed_app}.models")

        try:
            __import__(f"{installed_app}.background_tasks")
        except Exception as e:
            print("failing to import", installed_app, "bg tasks", e)

    ModelManager.initialise_models(_defined_in_test=True)
    initialise_database_driver(settings)
    _app = FastAPI(
        title=settings.PROJECT_NAME,
        swagger_ui_parameters={"defaultModelExpandDepth": 1, "deepLinking": True},
        lifespan=lifespan,
    )
    _app = setup_api_routes(_app, settings)
    _app = setup_user_routes(_app, settings)
    _app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    _app.add_middleware(GZipMiddleware, minimum_size=400)

    return _app
