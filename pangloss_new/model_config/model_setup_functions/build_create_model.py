import typing

from pydantic import create_model

from pangloss_new.model_config.field_definitions import RelationFieldDefinition
from pangloss_new.model_config.model_setup_functions.field_builders import (
    build_property_type_field,
)
from pangloss_new.model_config.model_setup_functions.utils import (
    get_concrete_model_types,
)
from pangloss_new.model_config.models_base import (
    CreateBase,
    ReifiedCreateBase,
    ReifiedRelation,
    RootNode,
)


def build_create_model(model: type[RootNode] | type[ReifiedRelation]):
    print(f"==== building for {model.__name__}")
    # Build fields
    fields = {}
    for field in model.__pg_field_definitions__.property_fields:
        if field.field_metatype == "PropertyField":
            fields[field.field_name] = build_property_type_field(field, model)

    for field in model.__pg_field_definitions__.relation_fields:
        if field.create_inline:
            pass
        else:
            fields[field.field_name] = build_relation_field(field, model)

    # Construct class
    if issubclass(model, ReifiedRelation):
        if not model.has_own("Create"):
            create_class = create_model(
                f"{model.__name__}Create", __base__=ReifiedCreateBase, **fields
            )

            model.Create = create_class

            model.Create.__pg_base_class__ = typing.cast(
                type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
            )

    else:
        model.Create = create_model(
            f"{model.__name__}Create", __base__=CreateBase, **fields
        )
        model.Create.__pg_base_class__ = model


def build_reified_create_model(model: type[ReifiedRelation]):
    fields = {}
    for field_name, field in model.model_fields.items():
        field_def = model.__pg_field_definitions__[field_name]
        assert field_def
        if field_def.field_metatype == "PropertyField":
            fields[field_name] = build_property_type_field(field_def, model)
        elif field_def.field_metatype == "RelationField":
            concrete_related_types = []
            concrete_types = get_concrete_model_types(
                field.annotation, include_subclasses=True
            )
            for concrete_type in concrete_types:
                if issubclass(concrete_type, ReifiedRelation):
                    if not concrete_type.has_own("Create"):
                        build_reified_create_model(concrete_type)
                    concrete_related_types.append(concrete_type.Create)
                else:
                    if concrete_type.Meta.create_by_reference:
                        concrete_related_types.append(concrete_type.ReferenceCreate)
                    concrete_related_types.append(concrete_type.ReferenceSet)

            if field_def.validators:
                fields[field_name] = (
                    typing.Annotated[
                        list[typing.Union[*concrete_related_types]],
                        *field_def.validators,
                    ],
                    ...,
                )
            else:
                fields[field_name] = (list[typing.Union[*concrete_related_types]], ...)
        model.Create = create_model(
            f"{model}Create", __base__=ReifiedCreateBase, **fields
        )


def build_relation_field(
    field: RelationFieldDefinition, model: type["RootNode"] | type["ReifiedRelation"]
):
    print(f"---building field {field.field_name}")
    concrete_model_types = []  # TODO: remove!!!

    # Build relations_to_nodes
    related_node_base_type = []
    for field_type_definition in field.relations_to_node:
        related_node_base_type.extend(
            get_concrete_model_types(
                field_type_definition.annotated_type,
                include_subclasses=True,
            )
        )
    for base_type in related_node_base_type:
        if field.create_inline:
            # Add creation model instead
            pass
        else:
            concrete_model_types.append(base_type.ReferenceSet)
            if base_type.Meta.create_by_reference:
                concrete_model_types.append(base_type.ReferenceCreate)

    # Build relations_to_typevars

    for field_type_definition in field.relations_to_reified:
        build_reified_create_model(field_type_definition.annotated_type)
        concrete_model_types.append(field_type_definition.annotated_type.Create)

    if field.validators:
        return (typing.Annotated[list[typing.Union[*concrete_model_types]]], ...)
    return (list[typing.Union[*concrete_model_types]], ...)
