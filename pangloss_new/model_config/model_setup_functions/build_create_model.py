import typing
from functools import cache

from pydantic import BaseModel, create_model

from pangloss_new.model_config.field_definitions import RelationFieldDefinition
from pangloss_new.model_config.model_setup_functions.field_builders import (
    build_property_type_field,
)
from pangloss_new.model_config.model_setup_functions.utils import (
    get_concrete_model_types,
)
from pangloss_new.model_config.models_base import (
    CreateBase,
    EdgeModel,
    ReifiedCreateBase,
    ReifiedRelation,
    RootNode,
)


def build_reified_model_name(model: type[ReifiedRelation]) -> str:
    origin_name = model.__pydantic_generic_metadata__["origin"].__name__
    args_names = [arg.__name__ for arg in model.__pydantic_generic_metadata__["args"]]
    return f"{origin_name}[{', '.join(args_names)}]"


def build_create_model(model: type[RootNode] | type[ReifiedRelation]):
    if model.has_own("Create"):
        return

    fields = {}
    for field in model._meta.fields.property_fields:
        if field.field_metatype == "PropertyField":
            fields[field.field_name] = build_property_type_field(field, model)

    for field in model._meta.fields.relation_fields:
        fields[field.field_name] = build_relation_field(field, model)

    # Construct class
    if issubclass(model, ReifiedRelation):
        model.Create = create_model(
            f"{build_reified_model_name(model)}Create",
            __module__=model.__module__,
            __base__=ReifiedCreateBase,
            **fields,
        )
        model.Create.__pg_base_class__ = typing.cast(
            type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
        )
    else:
        model.Create = create_model(
            f"{model.__name__}Create",
            __module__=model.__module__,
            __base__=CreateBase,
            **fields,
        )
        model.Create.__pg_base_class__ = model


@cache
def add_edge_model(model: type[BaseModel], edge_model: EdgeModel) -> type[BaseModel]:
    return create_model(
        f"{model.__name__}__via__{edge_model.__name__}",
        __base__=model,
        __module__=model.__module__,
        edge_properties=(edge_model, ...),
    )


def build_relation_field(
    field: RelationFieldDefinition, model: type["RootNode"] | type["ReifiedRelation"]
):
    concrete_model_types = []

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
            build_create_model(base_type)
            concrete_model_types.append(base_type.Create)
        else:
            concrete_model_types.append(base_type.ReferenceSet)
            if base_type.Meta.create_by_reference:
                concrete_model_types.append(base_type.ReferenceCreate)

    for field_type_definition in field.relations_to_reified:
        build_create_model(field_type_definition.annotated_type)
        concrete_model_types.append(field_type_definition.annotated_type.Create)

    if field.edge_model:
        concrete_model_types = [
            add_edge_model(t, field.edge_model) for t in concrete_model_types
        ]

    if field.validators:
        return (typing.Annotated[list[typing.Union[*concrete_model_types]]], ...)
    return (list[typing.Union[*concrete_model_types]], ...)


""" TODO: Remove once clear it is unnecessary
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
        )"""
