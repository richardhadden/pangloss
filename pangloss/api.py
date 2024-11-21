import typing
import uuid

from fastapi import FastAPI, APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel, AnyHttpUrl
from pydantic_settings import BaseSettings

from pangloss.model_config.model_manager import ModelManager
from pangloss.exceptions import PanglossNotFoundError
from pangloss.users import User, get_current_active_user
from pangloss.model_config.model_setup_utils import get_all_subclasses
from pangloss.models import BaseNode


class SuccessResponse(BaseModel):
    detail: str


class ErrorResponse(BaseModel):
    detail: str


class ListResponse[T](typing.TypedDict):
    results: typing.List[T]
    page: int
    count: int
    totalPages: int
    nextPage: int | None
    previousPage: int | None
    nextUrl: AnyHttpUrl | None
    previousUrl: AnyHttpUrl | None


def build_list_handler(model: type[BaseNode]):
    # Lists should also show any subclass of the model type,
    # so we need to allow this by getting all subclasses
    model_subclasses = get_all_subclasses(model)
    allowed_types = (
        typing.Union[*(m.ReferenceView for m in model_subclasses)]  # type: ignore
        if model_subclasses
        else model.ReferenceView
    )

    async def list(
        request: Request,
        # current_user: typing.Annotated[User, Depends(get_current_active_user)], # Don't lock down list view
        q: typing.Optional[str] = "",
        page: int = 1,
        pageSize: int = 50,
    ) -> ListResponse[allowed_types]:  # type: ignore
        # TODO add get_list method
        result = await model.get_list(q=q, page=page, page_size=pageSize)
        result["nextPage"] = page + 1 if page + 1 <= result["totalPages"] else None
        result["nextUrl"] = (
            str(request.url.replace_query_params(q=q, page=page + 1, pageSize=pageSize))
            if page + 1 <= result["totalPages"]
            else None
        )
        result["previousPage"] = page - 1 if page - 1 >= 1 else None
        result["previousUrl"] = (
            str(request.url.replace_query_params(q=q, page=page - 1, pageSize=pageSize))
            if page - 1 >= 1
            else None
        )
        return result

    return list


def build_delete_handler(model):
    async def delete(uid: uuid.UUID) -> None:
        raise HTTPException(status_code=501, detail="Not implemented yet")

    return delete


def build_get_handler(model):
    async def get(
        uuid: uuid.UUID,
    ) -> model.HeadView:  # type: ignore
        try:
            result = await model.get_view(uuid=uuid)
        except PanglossNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found")
        return result

    return get


def build_create_handler(Model: type[BaseNode]):
    async def create(
        request: Request,
        entity: Model,  # type: ignore
        current_user: typing.Annotated[User, Depends(get_current_active_user)],
    ) -> Model.ReferenceView:  # type: ignore
        result = await entity.create(current_username=current_user.username)
        return result

    return create


def build_get_edit_handler(model: type[BaseNode]):
    async def get_edit(uuid: uuid.UUID) -> model.EditView:  # type: ignore
        try:
            result = await model.get_edit_view(uuid=uuid)
        except PanglossNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found")
        return result

    return get_edit


def build_patch_edit_handler(model: type[BaseNode]):
    async def patch_edit(
        uuid: uuid.UUID,
        entity: model.EditSet,  # type: ignore
        current_user: typing.Annotated[User, Depends(get_current_active_user)],
    ) -> SuccessResponse:
        # Check the endpoint uuid matches the object uuid!
        if entity.uuid != uuid:
            raise HTTPException(status_code=400, detail="Bad request")

        try:
            await entity.update(username=current_user.username)
        except PanglossNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found")
        return SuccessResponse(detail="Update successful")

    return patch_edit


def setup_api_routes(_app: FastAPI, settings: BaseSettings) -> FastAPI:
    api_router = APIRouter(prefix="/api")
    for model in ModelManager.registered_models:
        router = APIRouter(prefix=f"/{model.__name__}", tags=[model.__name__])

        router.add_api_route(
            "/",
            endpoint=build_list_handler(model),
            methods={"get"},
            name=f"{model.__name__}.Index",
            operation_id=f"{model.__name__}Index",
            openapi_extra={"requiresAuth": True},
        )

        if not model.__abstract__:
            router.add_api_route(
                "/{uuid}",
                endpoint=build_get_handler(model),
                name=f"{model.__name__}.View",
                operation_id=f"{model.__name__}View",
            )

            if getattr(model, "__create__", False):
                router.add_api_route(
                    "/new",
                    endpoint=build_create_handler(model),
                    methods=["post"],
                    name=f"{model.__name__}.Create",
                    operation_id=f"{model.__name__}Create",
                )

            if getattr(model, "__edit__", False):
                router.add_api_route(
                    "/edit/{uuid}",
                    endpoint=build_get_edit_handler(model),
                    methods={"get"},
                    name=f"{model.__name__}.Edit.Get",
                    operation_id=f"{model.__name__}EditGet",
                )

                router.add_api_route(
                    "/edit/{uuid}",
                    endpoint=build_patch_edit_handler(model),
                    methods={"patch"},
                    name=f"{model.__name__}.Edit.Patch",
                    operation_id=f"{model.__name__}EditPatch",
                )

            if getattr(model, "__delete__", False):
                router.add_api_route(
                    "/{uuid}",
                    endpoint=build_delete_handler(model),
                    methods={"delete"},
                    name=f"{model.__name__}.Delete",
                )

        api_router.include_router(router)
    _app.include_router(api_router)
    return _app
