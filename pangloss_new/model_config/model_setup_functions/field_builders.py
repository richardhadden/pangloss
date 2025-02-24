import types
import typing

import pydantic.fields

from pangloss_new.model_config.models_base import ReifiedRelation, RootNode

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.field_definitions import (
        ListFieldDefinition,
        PropertyFieldDefinition,
    )


def build_property_type_field(
    field: "PropertyFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
) -> tuple[typing.Any, pydantic.fields.FieldInfo | types.EllipsisType | str]:
    if field.field_name == "type":
        return (
            field.field_annotation,
            pydantic.Field(default=model.__name__),
        )

    if field.validators:
        return (
            typing.Annotated[field.field_annotation, *field.validators],
            ...,
        )
    return (field.field_annotation, ...)


def build_list_property_type_field(
    field: "ListFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
):
    inner_type = field.field_annotation
    if field.internal_type_validators:
        inner_type = typing.Annotated[
            field.field_annotation, *field.internal_type_validators
        ]

    if field.validators:
        return (typing.Annotated[list[inner_type], *field.validators], ...)

    return (list[inner_type], ...)
