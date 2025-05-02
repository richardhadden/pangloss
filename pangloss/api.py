import typing

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from pydantic import AnyHttpUrl, BaseModel
from ulid import ULID

from pangloss.exceptions import PanglossNotFoundError
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_functions.utils import get_all_subclasses
from pangloss.model_config.models_base import CreateBase
from pangloss.models import BaseNode
from pangloss.neo4j.utils import SearchResultObject
from pangloss.users.routes import User, get_current_active_user

if typing.TYPE_CHECKING:
    from pangloss.settings import BaseSettings


LOCKED: set[ULID] = set()


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
    model_subclasses.add(model)
    allowed_types = (
        typing.Union[*(m.ReferenceView for m in model_subclasses)]  # type: ignore
        if model_subclasses
        else model.ReferenceView
    )

    async def list(
        request: Request,
        # current_user: typing.Annotated[User, Depends(get_current_active_user)], # Don't lock down list view
        q: str = "",
        page: int = 1,
        pageSize: int = 50,
    ) -> SearchResultObject[allowed_types]:  # type: ignore
        # TODO add get_list method
        result = await model.get_list(q=q, page=page, page_size=pageSize)

        result.next_page = page + 1 if page + 1 <= result.total_pages else None
        result.next_url = (
            typing.cast(
                AnyHttpUrl,
                request.url.replace_query_params(q=q, page=page + 1, pageSize=pageSize),
            )
            if page + 1 <= result.total_pages
            else None
        )
        result.previous_page = page - 1 if page - 1 >= 1 else None
        result.previous_url = (
            typing.cast(
                AnyHttpUrl,
                (
                    request.url.replace_query_params(
                        q=q, page=page - 1, pageSize=pageSize
                    )
                ),
            )
            if page - 1 >= 1
            else None
        )
        return result  # type: ignore

    return list


def build_delete_handler(model: type[BaseNode]):
    async def delete(id: ULID) -> None:
        raise HTTPException(status_code=501, detail="Not implemented yet")

    return delete


def build_get_handler(model: type["BaseNode"]):
    async def get(
        id: ULID | AnyHttpUrl,
    ) -> model.HeadView:  # type: ignore
        try:
            result = await model.get_view(id=id)
        except PanglossNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found")
        return result

    return get


def build_create_handler(model: type[BaseNode]):
    async def create(
        request: Request,
        entity: model.Create,  # type: ignore
        current_user: typing.Annotated[User, Depends(get_current_active_user)],
    ) -> model.ReferenceView:  # type: ignore
        entity = typing.cast(CreateBase, entity)
        result, deferred_query = await entity.create(
            username=current_user.username, use_deferred_query=True
        )
        LOCKED.add(result.id)
        await deferred_query()
        LOCKED.remove(result.id)
        return result

    return create


def build_get_edit_handler(model: type[BaseNode]):
    async def get_edit(id: ULID) -> model.EditHeadView:  # type: ignore
        try:
            result = await model.get_edit_view(id=id)
        except PanglossNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found")
        return result

    return get_edit


def build_patch_edit_handler(model: type[BaseNode]):
    async def patch_edit(
        id: ULID,
        entity: model.EditHeadSet,  # type: ignore
        current_user: typing.Annotated[User, Depends(get_current_active_user)],
    ) -> SuccessResponse:
        # Check the endpoint id matches the object id!
        if entity.id != id:
            raise HTTPException(status_code=400, detail="Bad request")

        try:
            await entity.update(username=current_user.username)
        except PanglossNotFoundError:
            raise HTTPException(status_code=404, detail="Item not found")
        return SuccessResponse(detail="Update successful")

    return patch_edit


def setup_api_routes(_app: FastAPI, settings: "BaseSettings") -> FastAPI:
    api_router = APIRouter(prefix="/api")
    for model in sorted(
        ModelManager.base_models.values(), key=lambda model: model.__name__
    ):
        router = APIRouter(
            prefix=f"/{model.__name__}",
            tags=[model.__name__],
        )

        router.add_api_route(
            "/",
            endpoint=build_list_handler(model),
            methods={"get"},
            name=f"{model.__name__}.Index",
            operation_id=f"{model.__name__}Index",
        )

        if not model._meta.abstract and model._meta.view:
            router.add_api_route(
                "/{id}",
                endpoint=build_get_handler(model),
                name=f"{model.__name__}.Get",
                operation_id=f"{model.__name__}Get",
            )

            if model.Meta.create:
                router.add_api_route(
                    "/new",
                    endpoint=build_create_handler(model),
                    methods=["post"],
                    name=f"{model.__name__}.Create",
                    operation_id=f"{model.__name__}Create",
                )

            if model.Meta.edit:
                router.add_api_route(
                    "/{id}/edit",
                    endpoint=build_get_edit_handler(model),
                    methods={"get"},
                    name=f"{model.__name__}.Edit.Get",
                    operation_id=f"{model.__name__}EditGet",
                )

                router.add_api_route(
                    "/{id}/edit",
                    endpoint=build_patch_edit_handler(model),
                    methods={"patch"},
                    name=f"{model.__name__}.Edit.Patch",
                    operation_id=f"{model.__name__}EditPatch",
                )

            if model.Meta.delete:
                router.add_api_route(
                    "/{id}",
                    endpoint=build_delete_handler(model),
                    methods={"delete"},
                    name=f"{model.__name__}.Delete",
                )

        api_router.include_router(router)
    _app.include_router(api_router)
    return _app
