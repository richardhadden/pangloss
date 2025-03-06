import typing
from functools import cache

from pydantic.fields import FieldInfo

from pangloss.model_config.models_base import ReifiedRelation, RootNode

if typing.TYPE_CHECKING:
    from pangloss.model_config.field_definitions import (
        ListFieldDefinition,
        MultiKeyFieldDefinition,
        PropertyFieldDefinition,
    )


def build_property_type_field(
    field: "PropertyFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
) -> FieldInfo:
    field_info = FieldInfo(annotation=field.field_annotation)

    if field.field_name == "type":
        field_info.default = model.__name__

    if field.validators:
        field_info.metadata = field.validators

    field_info.rebuild_annotation()
    return field_info


def build_list_property_type_field(
    field: "ListFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
) -> FieldInfo:
    inner_type = field.field_annotation
    if field.internal_type_validators:
        inner_type = typing.Annotated[
            field.field_annotation, *field.internal_type_validators
        ]

    field_info = FieldInfo.from_annotation(list[inner_type])

    if field.validators:
        field_info.metadata = field.validators

    return field_info


def build_multikey_property_type_field(
    field: "MultiKeyFieldDefinition", model: type[RootNode] | type[ReifiedRelation]
) -> FieldInfo:
    return FieldInfo.from_annotation(field.field_annotation)


@cache
def build_property_fields(model) -> dict[str, FieldInfo]:
    fields = {}
    for field in model._meta.fields.property_fields:
        if field.field_metatype == "PropertyField":
            fields[field.field_name] = build_property_type_field(field, model)
        elif field.field_metatype == "ListField":
            fields[field.field_name] = build_list_property_type_field(field, model)
        elif field.field_metatype == "MultiKeyField":
            fields[field.field_name] = build_multikey_property_type_field(field, model)
    return fields
