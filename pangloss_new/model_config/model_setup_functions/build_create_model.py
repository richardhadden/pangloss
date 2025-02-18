import typing

from pydantic import create_model

from pangloss_new.model_config.models_base import CreateBase, RootNode

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.field_definitions import (
        RelationFieldDefinition,
    )

from pangloss_new.model_config.model_setup_functions.field_builders import (
    build_property_type_field,
)


def build_relation_to_reference_field(
    field: "RelationFieldDefinition", model: type["RootNode"]
):
    pass


def build_create_model(model: type[RootNode]):
    fields = {}
    for field in model.__pg_field_definitions__.property_fields:
        if field.field_metatype == "PropertyField":
            fields[field.field_name] = build_property_type_field(field, model)

    for field in model.__pg_field_definitions__.relation_fields:
        if field.create_inline:
            pass
        else:
            pass
            # fields[field.field_name] = build_relation_to_reference_field(field, model)

    create_class = create_model(
        f"{model.__name__}Create", __base__=CreateBase, **fields
    )

    model.Create = create_class
