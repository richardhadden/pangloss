import types
import typing
from functools import cache

from pydantic import BaseModel, Field, create_model
from pydantic.fields import FieldInfo

from pangloss_new.model_config.field_definitions import (
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
)
from pangloss_new.model_config.model_setup_functions.field_builders import (
    build_property_fields,
)
from pangloss_new.model_config.model_setup_functions.utils import (
    get_base_models_for_relations_to_node,
    get_concrete_model_types,
)
from pangloss_new.model_config.models_base import (
    CreateBase,
    EdgeModel,
    EmbeddedCreateBase,
    ReferenceCreateBase,
    ReferenceSetBase,
    ReifiedCreateBase,
    ReifiedRelation,
    RootNode,
)


def build_reified_model_name(model: type[ReifiedRelation]) -> str:
    """Build a more elegant model name for reified models, omitting the module name
    and other ugliness"""
    origin_name = typing.cast(
        type, model.__pydantic_generic_metadata__["origin"]
    ).__name__
    args_names = [arg.__name__ for arg in model.__pydantic_generic_metadata__["args"]]
    return f"{origin_name}[{', '.join(args_names)}]"


def build_field_type_definitions(
    model: type[RootNode | ReifiedRelation],
):
    """For each type of possible field, build a dict of field name
    and pydantic tuple-type definition"""

    fields = {}
    fields.update(build_property_fields(model))

    for field in model._meta.fields.relation_fields:
        fields[field.field_name] = build_relation_field(field, model)

    for field in model._meta.fields.embedded_fields:
        fields[field.field_name] = build_embedded_field(field, model)

    return fields


def build_create_model(model: type[RootNode] | type[ReifiedRelation]):
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""
    print("building create model for ", model, model.has_own("Create"))
    # If model.Create already exists, return early
    if model.has_own("Create"):
        return

    # Gather field definitions

    # Construct class
    if issubclass(model, ReifiedRelation):
        fields = build_field_type_definitions(model)
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
        )
        fields = build_field_type_definitions(model)
        for field_name, annotation in fields.items():
            model.Create.model_fields[field_name] = FieldInfo.from_annotation(
                annotation[0]
            )
        model.Create.model_rebuild()
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


def get_models_for_relation_field(
    field: RelationFieldDefinition,
) -> list[type[ReferenceCreateBase | ReferenceSetBase | ReifiedCreateBase]]:
    """Creates a list of actual classes to be referenced by a relation"""
    related_models = []

    # Add relations_to_nodes to concrete_model_types
    for base_type in get_base_models_for_relations_to_node(field.relations_to_node):
        if field.create_inline:
            build_create_model(base_type)
            related_models.append(base_type.Create)
        else:
            related_models.append(base_type.ReferenceSet)
            if base_type.Meta.create_by_reference:
                related_models.append(base_type.ReferenceCreate)

    # Add relations_to_reified_to_concrete_model_Types
    for field_type_definition in field.relations_to_reified:
        build_create_model(field_type_definition.annotated_type)
        related_models.append(field_type_definition.annotated_type.Create)

    return related_models


def build_relation_field(
    field: RelationFieldDefinition, model: type["RootNode"] | type["ReifiedRelation"]
) -> (
    tuple[typing.Annotated, types.EllipsisType] | tuple[type[list], types.EllipsisType]
):
    related_models = get_models_for_relation_field(field)

    if field.edge_model:
        related_models = [add_edge_model(t, field.edge_model) for t in related_models]

    if field.validators:
        return (
            typing.Annotated[list[typing.Union[*related_models]], *field.validators],
            ...,
        )
    return (list[typing.Union[*related_models]], ...)


def build_embedded_create_model(model: type[RootNode]):
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""

    # If model.Create already exists, return early
    if model.has_own("EmbeddedCreate"):
        return

    # Gather field definitions
    fields = build_field_type_definitions(model)

    # Construct class
    if issubclass(model, ReifiedRelation):
        model.EmbeddedCreate = create_model(
            f"{build_reified_model_name(model)}Create",
            __module__=model.__module__,
            __base__=EmbeddedCreateBase,
            **fields,
        )
        model.EmbeddedCreate.__pg_base_class__ = typing.cast(
            type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
        )
    else:
        model.EmbeddedCreate = create_model(
            f"{model.__name__}Create",
            __module__=model.__module__,
            __base__=EmbeddedCreateBase,
            **fields,
        )
        model.EmbeddedCreate.__pg_base_class__ = model


def get_models_for_embedded_field(
    field: EmbeddedFieldDefinition,
) -> list[type[EmbeddedCreateBase]]:
    """Creates a list of actual classes to be embedded by a relation"""
    embedded_types = []

    for base_type in get_concrete_model_types(
        field.field_annotation, include_subclasses=True
    ):
        print(base_type)
        build_embedded_create_model(base_type)
        embedded_types.append(base_type.EmbeddedCreate)

    return embedded_types


def build_embedded_field(
    field: EmbeddedFieldDefinition, model: type["RootNode"] | type["ReifiedRelation"]
):
    embedded_types = get_models_for_embedded_field(field)

    return (
        typing.Annotated[list[typing.Union[*embedded_types]], *field.validators],
        Field(default_factory=list),
    )
