import typing

from pydantic import create_model
from pydantic.fields import FieldInfo

from pangloss.model_config.field_definitions import (
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.model_setup_functions.build_create_model import (
    build_create_model,
    build_embedded_create_model,
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
    EditHeadSetBase,
    EditSetBase,
    EmbeddedSetBase,
    EmbeddedViewBase,
    ReferenceCreateBase,
    ReferenceSetBase,
    ReifiedRelation,
    ReifiedRelationEditSetBase,
    RootNode,
)


def get_reified_model_name(model: type[ReifiedRelation]) -> str:
    """Build a more elegant model name for reified models, omitting the module name
    and other ugliness"""
    origin_name = typing.cast(
        type, model.__pydantic_generic_metadata__["origin"]
    ).__name__
    args_names = [arg.__name__ for arg in model.__pydantic_generic_metadata__["args"]]
    return f"{origin_name}[{', '.join(args_names)}]"


def get_field_type_definitions(
    model: type[RootNode | ReifiedRelation],
):
    """For each type of possible field, build a dict of field name
    and pydantic tuple-type definition"""

    fields = {}
    fields.update(build_property_fields(model))

    for field in model._meta.fields.relation_fields:
        fields[field.field_name] = get_relation_field(field)

    for field in model._meta.fields.embedded_fields:
        fields[field.field_name] = get_embedded_field(field)

    return fields


def build_edit_head_set_model(model: type[RootNode]):
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""

    # If model.Create already exists, return early
    if model.has_own("EditHeadSet"):
        return

    # Construct class

    # To avoid recursion of self-referencing models, the create model
    # needs to be built and *then* have its fields generated and added!
    model.EditHeadSet = create_model(
        f"{model.__name__}EditHeadSet",
        __module__=model.__module__,
        __base__=EditHeadSetBase,
    )

    unpack_fields_onto_model(model.EditHeadSet, get_field_type_definitions(model))
    model.EditHeadSet.__pg_base_class__ = model
    model.EditHeadSet.model_rebuild(force=True)


def build_edit_set_model(model: type[RootNode] | type[ReifiedRelation]):
    # If model.Create already exists, return early
    if model.has_own("EditSet"):
        return

    # Construct class
    if issubclass(model, ReifiedRelation):
        model.EditSet = create_model(
            f"{get_reified_model_name(model)}EditSet",
            __module__=model.__module__,
            __base__=ReifiedRelationEditSetBase,
        )

        unpack_fields_onto_model(model.EditSet, get_field_type_definitions(model))
        model.EditSet.__pg_base_class__ = typing.cast(
            type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
        )
        model.EditSet.model_rebuild(force=True)
    else:
        # To avoid recursion of self-referencing models, the create model
        # needs to be built and *then* have its fields generated and added!
        model.EditSet = create_model(
            f"{model.__name__}EditSet",
            __module__=model.__module__,
            __base__=EditSetBase,
        )

        unpack_fields_onto_model(model.EditSet, get_field_type_definitions(model))
        model.EditSet.__pg_base_class__ = model
        model.EditSet.model_rebuild(force=True)


def add_edge_model[
    T: type[ReferenceSetBase]
    | type[ReferenceCreateBase]
    | type[ReifiedRelationEditSetBase]
    | type[CreateBase]
    | type[EditSetBase]
](
    model: T,
    edge_model: type[EdgeModel],
) -> T:
    """Creates and returns a subclass of the model with the edge_model
    added as model.edge_properties field.

    Also stores the newly created model under model.via.<edge_model name>"""

    # To make sure models are actually the same, we need to check whether
    # the .via attribute of the model already contains this model;
    # no need to create in this case!
    if existing_edge_model := getattr(model.via, edge_model.__name__, None):
        return existing_edge_model

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
) -> list[
    type[
        ReferenceSetBase
        | ReferenceCreateBase
        | ReifiedRelationEditSetBase
        | CreateBase
        | EditSetBase
    ]
]:
    """Creates a list of actual classes to be referenced by a relation"""
    related_models = []

    # Add relations_to_nodes to concrete_model_types
    for base_type in get_base_models_for_relations_to_node(field.relations_to_node):
        if field.edit_inline:
            # If editable inline, it can either be a
            # setting of existing (EditSet) or new (Create)
            build_edit_set_model(base_type)
            related_models.append(base_type.EditSet)
            build_create_model(base_type)
            related_models.append(base_type.Create)
        else:
            if base_type._meta.create_by_reference:
                related_models.append(base_type.ReferenceCreate)
            related_models.append(base_type.ReferenceSet)

    # Add relations_to_reified_to_concrete_model_Types
    for field_type_definition in field.relations_to_reified:
        build_edit_set_model(field_type_definition.annotated_type)
        related_models.append(field_type_definition.annotated_type.EditSet)
        build_create_model(field_type_definition.annotated_type)
        related_models.append(field_type_definition.annotated_type.Create)

    return related_models


def get_relation_field(field: RelationFieldDefinition) -> FieldInfo:
    related_models = get_models_for_relation_field(field)

    if field.edge_model:
        related_models = [add_edge_model(t, field.edge_model) for t in related_models]

    # For unknown reasons, need to force rebuild models here
    for m in related_models:
        m.model_rebuild(force=True)

    field_info = FieldInfo.from_annotation(list[typing.Union[*related_models]])

    if field.validators:
        field_info.metadata = field.validators
    return field_info


def build_embedded_set_model(model: type[RootNode]) -> None:
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""

    # If model.Create already exists, return early
    if model.has_own("EmbeddedSet"):
        return

    model.EmbeddedSet = create_model(
        f"{model.__name__}EmbeddedSet",
        __module__=model.__module__,
        __base__=EmbeddedSetBase,
    )
    fields = get_field_type_definitions(model)
    for field_name, field_info in fields.items():
        model.EmbeddedSet.model_fields[field_name] = field_info
    model.EmbeddedSet.__pg_base_class__ = model
    model.EmbeddedSet.model_rebuild(force=True)


def get_models_for_embedded_field(
    field: EmbeddedFieldDefinition,
) -> list[type[EmbeddedViewBase]]:
    """Creates a list of actual classes to be embedded by a relation"""

    embedded_types = []

    for base_type in get_concrete_model_types(
        field.field_annotation, include_subclasses=True
    ):
        # Embedded can either be Set of existing or Create of new
        build_embedded_set_model(base_type)
        embedded_types.append(base_type.EmbeddedSet)
        build_embedded_create_model(base_type)
        embedded_types.append(base_type.EmbeddedCreate)

    return embedded_types


def get_embedded_field(field: EmbeddedFieldDefinition) -> FieldInfo:
    embedded_types = get_models_for_embedded_field(field)

    field_info = FieldInfo.from_annotation(list[typing.Union[*embedded_types]])
    if field.validators:
        field_info.metadata = field.validators
    return field_info
