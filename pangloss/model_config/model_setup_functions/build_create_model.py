import typing
from functools import cache

import humps
from pydantic import AliasChoices, BaseModel, create_model
from pydantic.fields import FieldInfo

from pangloss.model_config.field_definitions import (
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.model_setup_functions.field_builders import (
    build_property_fields,
)
from pangloss.model_config.model_setup_functions.utils import (
    get_base_models_for_relations_to_node,
    get_concrete_model_types,
    unpack_fields_onto_model,
)
from pangloss.model_config.models_base import (
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

    # If model.Create already exists, return early
    if model.has_own("Create"):
        return

    # Construct class
    if issubclass(model, ReifiedRelation):
        model.Create = create_model(
            f"{build_reified_model_name(model)}Create",
            __module__=model.__module__,
            __base__=ReifiedCreateBase,
        )

        unpack_fields_onto_model(model.Create, build_field_type_definitions(model))
        model.Create.__pg_base_class__ = typing.cast(
            type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
        )
        model.Create.model_rebuild(force=True)
    else:
        # To avoid recursion of self-referencing models, the create model
        # needs to be built and *then* have its fields generated and added!
        model.Create = create_model(
            f"{model.__name__}Create",
            __module__=model.__module__,
            __base__=CreateBase,
        )

        unpack_fields_onto_model(model.Create, build_field_type_definitions(model))
        model.Create.__pg_base_class__ = model
        model.Create.set_has_bindable_relations()
        model.Create.model_rebuild(force=True)


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

    # As fields are deferred being added, just inheriting from the model class does not work
    # and we need to manually add the fields and rebuild the model_with_edge
    model_with_edge.model_fields.update(model.model_fields)
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
) -> FieldInfo:
    related_models = get_models_for_relation_field(field)

    if field.edge_model:
        related_models = [add_edge_model(t, field.edge_model) for t in related_models]

    # For unknown reasons, need to force rebuild models here
    for m in related_models:
        m.model_rebuild(force=True)

    field_info = FieldInfo.from_annotation(list[typing.Union[*related_models]])
    if len(field.relation_labels) > 1:
        field_info.validation_alias = AliasChoices(
            *field.relation_labels, *(humps.camelize(l) for l in field.relation_labels)
        )
        field_info.alias_priority = 2

    if field.validators:
        field_info.metadata = field.validators
    return field_info


def build_embedded_create_model(model: type[RootNode]):
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""

    # If model.Create already exists, return early
    if model.has_own("EmbeddedCreate"):
        return

    model.EmbeddedCreate = create_model(
        f"{model.__name__}EmbeddedCreate",
        __module__=model.__module__,
        __base__=EmbeddedCreateBase,
    )
    fields = build_field_type_definitions(model)
    for field_name, field_info in fields.items():
        model.EmbeddedCreate.model_fields[field_name] = field_info
    model.EmbeddedCreate.__pg_base_class__ = model
    model.EmbeddedCreate.model_rebuild(force=True)


def get_models_for_embedded_field(
    field: EmbeddedFieldDefinition,
) -> list[type[EmbeddedCreateBase]]:
    """Creates a list of actual classes to be embedded by a relation"""
    embedded_types = []

    for base_type in get_concrete_model_types(
        field.field_annotation, include_subclasses=True
    ):
        build_embedded_create_model(base_type)
        embedded_types.append(base_type.EmbeddedCreate)

    return embedded_types


def build_embedded_field(
    field: EmbeddedFieldDefinition, model: type["RootNode"] | type["ReifiedRelation"]
) -> FieldInfo:
    embedded_types = get_models_for_embedded_field(field)
    field_info = FieldInfo.from_annotation(list[typing.Union[*embedded_types]])
    if field.validators:
        field_info.metadata = field.validators
    return field_info
