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
    ReferenceCreateBase,
    ReferenceSetBase,
    ReifiedCreateBase,
    ReifiedRelation,
    RootNode,
)


def build_reified_model_name(model: type[ReifiedRelation]) -> str:
    origin_name = typing.cast(
        type, model.__pydantic_generic_metadata__["origin"]
    ).__name__
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
def add_edge_model(
    model: type[ReferenceSetBase]
    | type[ReifiedCreateBase]
    | type[ReferenceCreateBase]
    | type[CreateBase],
    edge_model: EdgeModel,
) -> type[BaseModel]:
    """Creates and returns a subclass of the model with the edge_model
    added as model.edge_properties field.

    Also stores the newly created model under model.via.<edge_model name>"""
    model_with_edge = create_model(
        f"{model.__name__}__via__{edge_model.__name__}",
        __base__=model,
        __module__=model.__module__,
        edge_properties=(edge_model, ...),
    )

    model.via._add(edge_model_name=edge_model.__name__, model=model_with_edge)  # type: ignore
    return model_with_edge


def build_relation_field(
    field: RelationFieldDefinition, model: type["RootNode"] | type["ReifiedRelation"]
):
    concrete_model_types = []

    # Build relations_to_nodes
    related_node_base_type: list[type[RootNode]] = []
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
