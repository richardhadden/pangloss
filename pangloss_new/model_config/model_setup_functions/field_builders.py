import types
import typing

import pydantic.fields

from pangloss_new.model_config.models_base import ReifiedRelation, RootNode

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.field_definitions import PropertyFieldDefinition


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
