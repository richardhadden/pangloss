import asyncio
import contextlib
import logging
import sys

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from pangloss.auth import security
from pangloss.database import initialise_database_driver
from pangloss.settings import BaseSettings
from pangloss.users.routes import setup_user_routes

logger = logging.getLogger("uvicorn.info")
RunningBackgroundTasks = []


def get_application(settings: BaseSettings):
    DEVELOPMENT_MODE = "--reload" in sys.argv  # Dumb hack!

    from pangloss.api import setup_api_routes
    from pangloss.background_tasks import (
        BackgroundTaskCloseRegistry,
        BackgroundTaskRegistry,
    )
    from pangloss.initialisation import InitalisationTaskRegistery
    from pangloss.model_config.model_manager import ModelManager

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        # Load the ML model
        for task in BackgroundTaskRegistry:
            if not DEVELOPMENT_MODE or task["run_in_dev"]:
                running_task = asyncio.create_task(task["function"]())  # type: ignore

                RunningBackgroundTasks.append(running_task)
            else:
                logger.warning(
                    f"Skipping background task '{task['name']}' for development mode"
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
        except Exception:
            pass

        try:
            __import__(f"{installed_app}.initialisation")
        except Exception:
            pass

    ModelManager.initialise_models()
    initialise_database_driver(settings)
    _app: FastAPI = FastAPI(
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
    security.handle_errors(_app)
    for task in InitalisationTaskRegistery:
        logger.info(f"Initialising: {task['name']}")
        task["function"]()

    return _app
