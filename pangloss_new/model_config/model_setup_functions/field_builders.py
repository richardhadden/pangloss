import types
import typing
from functools import cache

import pydantic.fields

from pangloss_new.model_config.models_base import ReifiedRelation, RootNode

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.field_definitions import (
        ListFieldDefinition,
        MultiKeyFieldDefinition,
        PropertyFieldDefinition,
    )


def build_property_type_field(
    field: "PropertyFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
) -> tuple[typing.Any, pydantic.fields.FieldInfo | types.EllipsisType | str]:
    if field.field_name == "type":
        return (
            typing.Annotated[
                field.field_annotation, pydantic.Field(default=model.__name__)
            ],
            ...,
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


def build_multikey_property_type_field(
    field: "MultiKeyFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
):
    return (field.field_annotation, ...)


@cache
def build_property_fields(model):
    fields = {}
    for field in model._meta.fields.property_fields:
        if field.field_metatype == "PropertyField":
            fields[field.field_name] = build_property_type_field(field, model)
        elif field.field_metatype == "ListField":
            fields[field.field_name] = build_list_property_type_field(field, model)
        elif field.field_metatype == "MultiKeyField":
            fields[field.field_name] = build_multikey_property_type_field(field, model)
    return fields
