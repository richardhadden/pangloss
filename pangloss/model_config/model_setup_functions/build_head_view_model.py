import typing
from functools import cache

from pydantic import create_model
from pydantic.fields import FieldInfo

from pangloss.model_config.field_definitions import (
    ContextIncomingRelationDefinition,
    DirectIncomingRelationDefinition,
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
    EdgeModel,
    EmbeddedViewBase,
    HeadViewBase,
    ReferenceViewBase,
    ReifiedRelation,
    ReifiedRelationViewBase,
    RootNode,
    ViewBase,
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


def build_head_view_model(model: type[RootNode]):
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""

    # If model.Create already exists, return early
    if model.has_own("HeadView"):
        return

    # Construct class

    # To avoid recursion of self-referencing models, the create model
    # needs to be built and *then* have its fields generated and added!
    model.HeadView = create_model(
        f"{model.__name__}HeadView",
        __module__=model.__module__,
        __base__=HeadViewBase,
    )

    unpack_fields_onto_model(model.HeadView, get_field_type_definitions(model))

    model.HeadView.__pg_base_class__ = model

    build_reverse_relations_for_model(model.HeadView)
    model.HeadView.model_rebuild(force=True)


def build_view_model(model: type[RootNode] | type[ReifiedRelation]):
    # If model.Create already exists, return early
    if model.has_own("View"):
        return

    # Construct class
    if issubclass(model, ReifiedRelation):
        model.View = create_model(
            f"{get_reified_model_name(model)}View",
            __module__=model.__module__,
            __base__=ReifiedRelationViewBase,
        )

        unpack_fields_onto_model(model.View, get_field_type_definitions(model))
        model.View.__pg_base_class__ = typing.cast(
            type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
        )
        model.View.model_rebuild(force=True)
    else:
        # To avoid recursion of self-referencing models, the create model
        # needs to be built and *then* have its fields generated and added!
        model.View = create_model(
            f"{model.__name__}View",
            __module__=model.__module__,
            __base__=ViewBase,
        )

        unpack_fields_onto_model(model.View, get_field_type_definitions(model))
        model.View.__pg_base_class__ = model

        model.View.model_rebuild(force=True)


@cache
def add_edge_model[T: type[ReferenceViewBase] | type[ReifiedRelationViewBase]](
    model: T,
    edge_model: EdgeModel,
) -> T:
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
) -> list[type[ReferenceViewBase | ReifiedRelationViewBase]]:
    """Creates a list of actual classes to be referenced by a relation"""
    related_models = []

    # Add relations_to_nodes to concrete_model_types
    for base_type in get_base_models_for_relations_to_node(field.relations_to_node):
        if field.edit_inline:
            build_view_model(base_type)
            related_models.append(base_type.View)
        else:
            related_models.append(base_type.ReferenceView)

    # Add relations_to_reified_to_concrete_model_Types
    for field_type_definition in field.relations_to_reified:
        build_view_model(field_type_definition.annotated_type)
        related_models.append(field_type_definition.annotated_type.View)

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


def build_embedded_view_model(model: type[RootNode]) -> None:
    """Builds model.Create for a RootNode/ReifiedRelation where it does not exist"""

    # If model.Create already exists, return early
    if model.has_own("EmbeddedView"):
        return

    model.EmbeddedView = create_model(
        f"{model.__name__}EmbeddedView",
        __module__=model.__module__,
        __base__=EmbeddedViewBase,
    )
    fields = get_field_type_definitions(model)
    for field_name, field_info in fields.items():
        model.EmbeddedView.model_fields[field_name] = field_info
    model.EmbeddedView.__pg_base_class__ = model
    model.EmbeddedView.model_rebuild(force=True)


def get_models_for_embedded_field(
    field: EmbeddedFieldDefinition,
) -> list[type[EmbeddedViewBase]]:
    """Creates a list of actual classes to be embedded by a relation"""

    embedded_types = []

    for base_type in get_concrete_model_types(
        field.field_annotation, include_subclasses=True
    ):
        build_embedded_view_model(base_type)
        embedded_types.append(base_type.EmbeddedView)

    return embedded_types


def get_embedded_field(field: EmbeddedFieldDefinition) -> FieldInfo:
    embedded_types = get_models_for_embedded_field(field)

    field_info = FieldInfo.from_annotation(list[typing.Union[*embedded_types]])
    if field.validators:
        field_info.metadata = field.validators
    return field_info


def build_reverse_relations_for_model(model_head_view: type[HeadViewBase]) -> None:
    assert issubclass(model_head_view.__pg_base_class__, RootNode)
    if not model_head_view.__pg_base_class__._meta.reverse_relations:
        return
    for (
        reverse_relation_field_name,
        reverse_relation_definition_set,
    ) in model_head_view.__pg_base_class__._meta.reverse_relations.items():
        concrete_classes_for_field = []
        for reverse_relation_definition in reverse_relation_definition_set:
            if isinstance(
                reverse_relation_definition, DirectIncomingRelationDefinition
            ):
                concrete_classes_for_field.append(
                    build_direct_reverse_relation(reverse_relation_definition)
                )
            elif isinstance(
                reverse_relation_definition, ContextIncomingRelationDefinition
            ):
                concrete_classes_for_field.append(
                    build_context_reverse_relation(
                        target_model=model_head_view.__pg_base_class__,
                        reverse_relation_definition=reverse_relation_definition,
                    )
                )

        model_head_view.model_fields[reverse_relation_field_name] = (
            FieldInfo.from_annotation(list[typing.Union[*concrete_classes_for_field]])
        )
        model_head_view.model_fields[reverse_relation_field_name].default_factory = list
    model_head_view.model_rebuild(force=True)


# Event.View.in_context_of.Cat.is_involved_in = ContextViewModel
#           ^target


def build_context_reverse_relation(
    target_model: type[RootNode],
    reverse_relation_definition: ContextIncomingRelationDefinition,
):
    build_view_model(reverse_relation_definition.reverse_target)

    context_reverse_relation_model_name = (
        f"{reverse_relation_definition.reverse_target.__name__}View"
        f"__in_context_of__{target_model.__name__}"
        f"__{reverse_relation_definition.reverse_name}"
    )
    # THIS HERE should not be [1] but the next that is not an Embedded...
    next_not_embedded_index = 1
    for i, segment in enumerate(
        reverse_relation_definition.forward_path_object[1:-1], start=1
    ):
        if (
            segment.metatype == "EmbeddedNode"
            and reverse_relation_definition.forward_path_object[i + 1].metatype
            != "EmbeddedNode"
        ):
            next_not_embedded_index = i + 1

    context_type_base = reverse_relation_definition.forward_path_object[
        next_not_embedded_index
    ].type

    build_view_model(context_type_base)
    context_type = context_type_base.View

    if (
        hasattr(reverse_relation_definition.relation_definition, "edge_model")
        and reverse_relation_definition.relation_definition.edge_model
    ):
        context_type = add_edge_model(
            context_type, reverse_relation_definition.relation_definition.edge_model
        )

    context_field_def = {
        reverse_relation_definition.relation_definition.field_name: (
            list[context_type],
            ...,
        )
    }

    context_reverse_relation_model = create_model(  # type: ignore
        context_reverse_relation_model_name,
        __base__=ViewBase,
        **context_field_def,  # type: ignore
    )

    reverse_relation_definition.reverse_target.View.in_context_of._add(
        relation_target_model=target_model,
        view_in_context_model=context_reverse_relation_model,
        reverse_field_name=reverse_relation_definition.reverse_name,
    )

    return context_reverse_relation_model


def build_direct_reverse_relation(
    reverse_relation_definition: DirectIncomingRelationDefinition,
):
    if reverse_relation_definition.relation_definition.edge_model:
        return add_edge_model(
            reverse_relation_definition.reverse_target.ReferenceView,
            reverse_relation_definition.relation_definition.edge_model,
        )

    return reverse_relation_definition.reverse_target.ReferenceView
