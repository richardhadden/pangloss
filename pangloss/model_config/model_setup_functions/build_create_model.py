import typing
import warnings
from functools import cache

import humps
from pydantic import AliasChoices, BaseModel, create_model, model_validator
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
    model: type[RootNode | ReifiedRelation], bound_field_names: set[str] | None = None
):
    """For each type of possible field, build a dict of field name
    and pydantic tuple-type definition"""

    fields = {}
    fields.update(build_property_fields(model, bound_field_names))

    for field in model._meta.fields.relation_fields:
        if bound_field_names and field.field_name in bound_field_names:
            fields[field.field_name] = build_relation_field(field, model, True)
        else:
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


@model_validator(mode="after")
def bound_field_creation_model_after_validator(self: "CreateBase") -> typing.Any:
    """Validator to validate the created object after the fields have
    been bound"""
    self.__pg_base_class__.Create.model_validate(self)
    return self


def build_bound_field_creation_model(
    field: RelationFieldDefinition,
    parent_model: type[RootNode] | type[ReifiedRelation],
    base_type_for_bound_model: type[RootNode],
    bound_relation_field_names: set[str],
):
    """Creates a variant of a model (base_type_for_bound_models) with the fields
    that are bound to the parent made optional. Also adds a validator function that
    checks the data from parent-bound fields are included"""

    # Bug with Pydantic: adding __validators__ (as per documentation) causes a
    # runtime warning that fields should not start with an underscore... but of course it can
    # so suppress the warning here
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")

        # Create a new model
        bound_field_model = create_model(
            f"{base_type_for_bound_model.__name__}_Create__in_context_of__{parent_model.__name__}__{field.field_name}",
            __base__=base_type_for_bound_model.Create,
            __model__=base_type_for_bound_model.__module__,
            __validators__={
                "post_validator": typing.cast(
                    typing.Callable, bound_field_creation_model_after_validator
                )
            },
        )

    build_field_type_definitions(base_type_for_bound_model)

    unpack_fields_onto_model(
        bound_field_model,
        build_field_type_definitions(
            base_type_for_bound_model, bound_relation_field_names
        ),
    )
    bound_field_model.__pg_base_class__ = base_type_for_bound_model
    bound_field_model.model_rebuild(force=True)

    # Register the model using the Create.in_context_of mechanism
    base_type_for_bound_model.Create.in_context_of._add(
        relation_target_model=parent_model,
        view_in_context_model=bound_field_model,
        field_name=field.field_name,
    )

    return bound_field_model


# Event.View.in_context_of.Cat.is_involved_in = ContextViewModel
#           ^target


def get_models_for_relation_field(
    field: RelationFieldDefinition,
    parent_model: type[RootNode] | type[ReifiedRelation],
    bound_relation_field_names: set[str] | None = None,
) -> list[type[ReferenceCreateBase | ReferenceSetBase | ReifiedCreateBase]]:
    """Creates a list of actual classes to be referenced by a relation"""
    related_models = []

    # Add relations_to_nodes to concrete_model_types
    for base_type in get_base_models_for_relations_to_node(field.relations_to_node):
        if field.create_inline:
            build_create_model(base_type)

            # Check if any of the fields bound to parent_model field are in this model,
            # and if so, create a bound_field_model instead of the usual one
            if bound_relation_field_names and any(
                bf in base_type._meta.fields for bf in bound_relation_field_names
            ):
                bound_field_model = build_bound_field_creation_model(
                    field, parent_model, base_type, bound_relation_field_names
                )
                related_models.append(bound_field_model)

            else:
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


@cache
def get_bound_relation_field_names_for_bound(
    model: type["RootNode"],
) -> set[str]:
    bound_relations = [
        rf for rf in model._meta.fields.relation_fields if rf.bind_fields_to_related
    ]
    bound_relation_field_names = set()
    for bound_relation in bound_relations:
        assert bound_relation.bind_fields_to_related
        bound_relation_field_names.update(
            br[1] for br in bound_relation.bind_fields_to_related
        )
    return bound_relation_field_names


def build_relation_field(
    field: RelationFieldDefinition,
    model: type["RootNode"] | type["ReifiedRelation"],
    is_bound: bool = False,
) -> FieldInfo:
    # Get the relations which are fields bound to this model
    bound_fields = get_bound_relation_field_names_for_bound(model)

    related_models = get_models_for_relation_field(field, model, bound_fields)

    if field.edge_model:
        related_models = [add_edge_model(t, field.edge_model) for t in related_models]

    # For unknown reasons, need to force rebuild models here
    for m in related_models:
        m.model_rebuild(force=True)

    if (
        is_bound
    ):  # If the field is bound to value from parent field, make this field optional
        field_info = FieldInfo.from_annotation(
            typing.cast(
                type[typing.Any], typing.Optional[list[typing.Union[*related_models]]]
            )
        )
        field_info.default = None
        field_info.rebuild_annotation()
    else:
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
