import dataclasses
import inspect
import types
import typing
import uuid

import pydantic

from pangloss.exceptions import PanglossConfigError
from pangloss.model_config.field_definitions import (
    IncomingRelationDefinition,
    ModelFieldDefinitions,
    FieldDefinition,
    LiteralFieldDefinition,
    ListFieldDefinition,
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.models_base import (
    EmbeddedSetBase,
    EmbeddedViewBase,
    RootNode,
    Embedded,
    RelationConfig,
    ReifiedRelation,
    ReifiedRelationNonTargetPointer,
    HeritableTrait,
    NonHeritableTrait,
    ReferenceSetBase,
    ReferenceViewBase,
    ViewBase,
)
from pangloss.model_config.model_setup_utils import (
    PathToTargetRootNode,
    create_reference_view_model_with_property_model,
    get_non_heritable_traits_as_indirect_ancestors,
    create_reference_set_model_with_property_model,
    get_paths_to_target_node,
)


def get_relation_config_from_field_metadata(
    field_metadata: list[typing.Any],
) -> RelationConfig | None:
    try:
        return [
            metadata_item
            for metadata_item in field_metadata
            if isinstance(metadata_item, RelationConfig)
        ][0]
    except IndexError:
        return None


def set_type_to_literal_on_base_model(cls: type[RootNode] | type[ReifiedRelation]):
    cls.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore
    cls.model_fields["type"].default = cls.__name__


def is_relation_field(
    type_origin,
    field_annotation,
    field_metadata,
    field_name: str,
    model: type["RootNode"] | type["ReifiedRelation"],
) -> bool:
    relation_config = get_relation_config_from_field_metadata(field_metadata)

    # If annotation type is a Union
    if type_origin is types.UnionType and relation_config:
        union_types = typing.get_args(field_annotation)

        # Check all args to Union are RootNode or ReifiedRelation subclasses
        if all(
            (
                inspect.isclass(t)
                and issubclass(
                    t, (RootNode, ReifiedRelation, HeritableTrait, NonHeritableTrait)
                )
            )
            for t in union_types
        ):
            return True

        # Otherwise, throw an error
        else:
            raise PanglossConfigError(
                f"Field '{field_name}' on model '{model.__name__}' is a union of types that are not a BaseNode or ReifiedRelation"
            )

    # If annotation type is a ReifiedRelation...
    if (
        field_annotation
        and inspect.isclass(field_annotation)
        and issubclass(field_annotation, ReifiedRelation)
        and relation_config
    ):
        return True

    # If annotation type is a RootNode or Trait...
    if (
        field_annotation
        and inspect.isclass(field_annotation)
        and issubclass(field_annotation, (RootNode, HeritableTrait, NonHeritableTrait))
        and relation_config
    ):
        return True
    return False


def build_field_definition_from_annotation(
    model: type[RootNode] | type[ReifiedRelation],
    field_name: str,
    field: pydantic.fields.FieldInfo,
) -> FieldDefinition:
    # If the model is a Generic, the field annotation will be a TypeVar;
    # in this case, we need to extract the type arguments to the origin class and
    # change the field.annotation to be the right index of the model arg
    if type(field.annotation) is typing.TypeVar:
        origin = typing.cast(
            type[ReifiedRelation], model.__pydantic_generic_metadata__["origin"]
        )
        origin_typevars = origin.__pydantic_generic_metadata__["parameters"]
        typevar_index = [str(p) for p in origin_typevars].index(str(field.annotation))
        field.annotation = model.__pydantic_generic_metadata__["args"][typevar_index]

    type_origin = typing.get_origin(field.annotation)

    # Guard clauses:
    #   If it is a relation and no RelationConfig provided, die
    #   If it's a union of relations and no RelationConfig, die
    #   If it's a union of normal types, die
    # Guard clauses do unnecessary work, and are only required to stop the fallthrough to
    # using a standard property type; so they are moved to being the penultimate option

    # Type is a relation
    if (
        field.annotation
        and is_relation_field(
            type_origin=type_origin,
            field_annotation=field.annotation,
            field_metadata=field.metadata,
            field_name=field_name,
            model=model,
        )
        and (relation_config := get_relation_config_from_field_metadata(field.metadata))
    ):
        validators = [
            metadata_item
            for metadata_item in field.metadata
            if not isinstance(metadata_item, RelationConfig)
        ]
        validators = [*validators, *relation_config.validators]

        relation_config_dict = dataclasses.asdict(relation_config)
        del relation_config_dict["validators"]
        return RelationFieldDefinition(
            field_name=field_name,
            field_annotated_type=field.annotation,
            validators=validators,
            **relation_config_dict,
        )

    # Type is an embedded node
    elif type_origin is Embedded:
        typing_args = typing.get_args(field.annotation)
        if not typing_args or (
            inspect.isclass(typing_args[0]) and not issubclass(typing_args[0], RootNode)
        ):
            raise PanglossConfigError(
                f"Error with field '{field_name}' on model '{model.__name__}':"
                "the type argument of Embedded must be a subclass of BaseNode"
            )

        return EmbeddedFieldDefinition(
            field_name=field_name,
            field_annotated_type=typing.get_args(field.annotation)[0],
            validators=field.metadata,
        )

    # Type is a list of literal types
    elif (
        inspect.isclass(type_origin)
        and issubclass(type_origin, typing.Iterable)
        and typing.get_args(field.annotation)
    ):
        return ListFieldDefinition(
            field_name=field_name,
            field_annotated_type=typing.get_args(field.annotation)[0],
            validators=field.metadata,
        )

    # Guard clauses before we fall back to treating the annotation as a proper literal type

    # If annotation is a RootNode subclass, and there is no RelationConfig provided
    elif (
        field.annotation
        and inspect.isclass(field.annotation)
        and issubclass(
            field.annotation,
            (RootNode, ReifiedRelation, HeritableTrait, NonHeritableTrait),
        )
        and not get_relation_config_from_field_metadata(field.metadata)
    ):
        raise PanglossConfigError(
            f"Field '{field_name}' on model '{model.__name__}' is missing a RelationConfig annotation"
        )

    elif type_origin is types.UnionType:
        if all(
            issubclass(
                t, (RootNode, ReifiedRelation, HeritableTrait, NonHeritableTrait)
            )
            for t in typing.get_args(field.annotation)
        ) and not get_relation_config_from_field_metadata(field.metadata):
            raise PanglossConfigError(
                f"Field '{field_name}' on model '{model.__name__}' is missing a RelationConfig annotation"
            )
        else:
            raise PanglossConfigError(
                f"Error with field '{field_name}' on model '{model.__name__}': Property fields do not support Union types"
            )

    # Any other annotation, assume it's a literal type

    elif field.annotation:
        return LiteralFieldDefinition(
            field_name=field_name,
            field_annotated_type=field.annotation,  # type: ignore
            validators=field.metadata,
        )

    raise Exception("Field type not caught")


def initialise_model_field_definitions(
    cls: type[RootNode] | type[ReifiedRelation],
):
    """Creates a model field_definition object for each field
    of a model"""

    cls.field_definitions = ModelFieldDefinitions()

    for field_name, field in cls.model_fields.items():
        cls.field_definitions[field_name] = build_field_definition_from_annotation(
            model=cls, field_name=field_name, field=field
        )


def delete_indirect_non_heritable_trait_fields(
    cls: type[RootNode],
) -> None:
    trait_fields_to_delete = set()
    for trait in get_non_heritable_traits_as_indirect_ancestors(cls):
        for field_name in cls.model_fields:
            # TODO: AND AND... not in the parent class annotations that is *not* a trait...
            if field_name in trait.__annotations__ and trait not in cls.__annotations__:
                trait_fields_to_delete.add(field_name)
    for td in trait_fields_to_delete:
        del cls.model_fields[td]


def initialise_reference_set_on_base_models(cls: type[RootNode]):
    # If ReferenceSet manually defined on a class, and it's a subclass of
    # ReferenceSetBase, just override the `type` field to the class name
    if (
        getattr(cls, "ReferenceSet", None)
        and inspect.isclass(cls.ReferenceSet)
        and issubclass(cls.ReferenceSet, ReferenceSetBase)
    ):
        cls.ReferenceSet.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore
        cls.ReferenceSet.model_fields["type"].default = cls.__name__
        cls.ReferenceSet.base_class = cls
        return

    # If ReferenceSet is manually defined but does not fulfil requirement above (subclassing
    # ReferenceViewSet), raise an error
    if getattr(cls, "ReferenceSet", None):
        raise PanglossConfigError(
            f"ReferenceSet defined on model '{cls.__name__}' must be class inheriting from pangloss.models.ReferenceSet"
        )

    # Otherwise, construct a ReferenceSet class
    cls.ReferenceSet = pydantic.create_model(
        f"{cls.__name__}ReferenceSet",
        __base__=ReferenceSetBase,
        type=(typing.Literal[cls.__name__], cls.__name__),  # type: ignore
    )
    cls.ReferenceSet.base_class = cls


def initialise_reference_view_on_base_models(cls: type[RootNode]):
    # If ReferenceView manually defined on a class, and it is a subclass
    # of ReferenceViewBase, just override the `type` field to the class name
    if (
        getattr(cls, "ReferenceView", None)
        and inspect.isclass(cls.ReferenceView)
        and issubclass(cls.ReferenceView, ReferenceViewBase)
    ):
        cls.ReferenceView.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore
        cls.ReferenceView.model_fields["type"].default = cls.__name__
        cls.ReferenceView.base_class = cls
        return

    # If ReferenceView is manually defined but does not fulfil requirement above (subclassing
    # ReferenceViewBase), raise an error
    if getattr(cls, "ReferenceView", None):
        raise PanglossConfigError(
            f"ReferenceView defined on model '{cls.__name__}' must be class inheriting from pangloss.models.ReferenceView"
        )

    # Otherwise, construct a ReferenceView class
    cls.ReferenceView = pydantic.create_model(
        f"{cls.__name__}ReferenceView",
        __base__=ReferenceViewBase,
        type=(typing.Literal[cls.__name__], cls.__name__),  # type: ignore
    )
    cls.ReferenceView.base_class = cls


def initialise_outgoing_relation_types_on_base_model(
    cls: type[RootNode] | type[ReifiedRelation],
):
    """Convert Relation fields on a model to ReferenceSet types or ReifiedRelation,
    if necessary constructing a new field-specific type if a RelationPropertyModel
    is added"""

    for field in cls.field_definitions.relation_fields:
        reference_types = []
        for concrete_type in field.field_concrete_types:
            if issubclass(concrete_type, RootNode):
                if field.create_inline and field.relation_model:
                    create_inline_model_with_relation_model = pydantic.create_model(
                        f"{cls.__name__}__{field.field_name}__{concrete_type.__name__}__CreateInline",
                        __base__=concrete_type,
                        relation_properties=(field.relation_model, ...),
                    )
                    reference_types.append(create_inline_model_with_relation_model)
                elif field.create_inline:
                    reference_types.append(concrete_type)
                elif field.relation_model:
                    reference_types.append(
                        create_reference_set_model_with_property_model(
                            origin_model=cls,
                            target_model=concrete_type,
                            relation_model=field.relation_model,
                            field_name=field.field_name,
                        )
                    )
                else:
                    reference_types.append(concrete_type.ReferenceSet)

            if issubclass(concrete_type, ReifiedRelation):
                if field.relation_model:
                    initialise_reified_relation(concrete_type)
                    reified_relation_model_with_relation_property_model = pydantic.create_model(
                        f"{cls.__name__}__{field.field_name}__{concrete_type.__name__}",
                        __base__=concrete_type,
                        relation_properties=(field.relation_model, ...),
                    )
                    reference_types.append(
                        reified_relation_model_with_relation_property_model
                    )
                else:
                    initialise_reified_relation(concrete_type)
                    reference_types.append(concrete_type)

        cls.model_fields[field.field_name].annotation = list[
            typing.Union[
                *reference_types  # type: ignore
            ]
        ]
        cls.model_fields[field.field_name].discriminator = "type"

        cls.model_fields[field.field_name].metadata = field.validators


def create_embedded_set_model(cls: type[RootNode]):
    embedded_set_model = pydantic.create_model(
        f"{cls.__name__}EmbeddedSet", __base__=EmbeddedSetBase
    )
    embedded_set_model.base_class = cls

    fields = {
        field_name: field
        for field_name, field in cls.model_fields.items()
        if field_name != "label"
    }
    embedded_set_model.model_fields = fields
    embedded_set_model.model_rebuild(force=True)

    # It should not be necessary to initialise anything on this model
    # as it inherits the already-initialised fields from its container base class

    return embedded_set_model


def create_embedded_view_model(cls: type[RootNode]):
    embedded_set_model = pydantic.create_model(
        f"{cls.__name__}EmbeddedView", __base__=EmbeddedViewBase
    )
    embedded_set_model.base_class = cls

    fields = {
        field_name: field
        for field_name, field in cls.model_fields.items()
        if field_name != "label"
    }
    embedded_set_model.model_fields = fields
    embedded_set_model.model_rebuild(force=True)

    # It should not be necessary to initialise anything on this model
    # as it inherits the already-initialised fields from its container base class

    return embedded_set_model


def initialise_embedded_nodes_on_base_model(
    cls: type[RootNode] | type[ReifiedRelation],
):
    for embedded_field_definition in cls.field_definitions.embedded_fields:
        embedded_models = []
        for embedded_type in embedded_field_definition.field_concrete_types:
            if not getattr(embedded_type, "EmbeddedSet", None):
                embedded_type.EmbeddedSet = create_embedded_set_model(embedded_type)
            embedded_models.append(embedded_type.EmbeddedSet)

        cls.model_fields[embedded_field_definition.field_name].annotation = list[
            typing.Union[*embedded_models]  # type: ignore
        ]
        cls.model_fields[
            embedded_field_definition.field_name
        ].metadata = embedded_field_definition.validators
        cls.model_fields[embedded_field_definition.field_name].discriminator = "type"


def initialise_reified_relation(reified_relation: type[ReifiedRelation]):
    if not getattr(reified_relation, "field_definitions", None):
        set_type_to_literal_on_base_model(reified_relation)
        initialise_model_field_definitions(reified_relation)
        initialise_outgoing_relation_types_on_base_model(reified_relation)
        initialise_view_type_for_base(reified_relation)


def initialise_relation_fields_on_view_model(
    cls: type[RootNode] | type[ReifiedRelation],
):
    # Add relation fields
    for relation_field_definition in cls.field_definitions.relation_fields:
        referenced_types = []
        for concrete_type in relation_field_definition.field_concrete_types:
            if issubclass(concrete_type, RootNode):
                initialise_view_type_for_base(concrete_type)

                if (
                    relation_field_definition.create_inline
                    and relation_field_definition.relation_model
                ):
                    create_inline_model_with_relation_model = pydantic.create_model(
                        f"{cls.__name__}__{relation_field_definition.field_name}__{concrete_type.__name__}__ViewInline",
                        __base__=concrete_type.View,
                        relation_properties=(
                            relation_field_definition.relation_model,
                            ...,
                        ),
                    )
                    referenced_types.append(create_inline_model_with_relation_model)
                elif relation_field_definition.create_inline:
                    referenced_types.append(concrete_type.View)

                elif relation_field_definition.relation_model:
                    referenced_types.append(
                        create_reference_view_model_with_property_model(
                            origin_model=cls,
                            target_model=concrete_type,
                            relation_model=relation_field_definition.relation_model,
                            field_name=relation_field_definition.field_name,
                        )
                    )
                else:
                    referenced_types.append(concrete_type.ReferenceView)
            if issubclass(concrete_type, ReifiedRelation):
                initialise_view_type_for_base(concrete_type)
                if relation_field_definition.relation_model:
                    reified_relation_view_model_with_relation_property_model = pydantic.create_model(
                        f"{cls.__name__}__{relation_field_definition.field_name}__{concrete_type.__name__}__View",
                        __base__=concrete_type.View,
                        relation_properties=(
                            relation_field_definition.relation_model,
                            ...,
                        ),
                    )
                    referenced_types.append(
                        reified_relation_view_model_with_relation_property_model
                    )
                else:
                    referenced_types.append(concrete_type.View)

        cls.View.model_fields[relation_field_definition.field_name] = (
            pydantic.fields.FieldInfo.from_annotation(
                list[
                    typing.Union[
                        *referenced_types  # type: ignore
                    ]
                ]
            )
        )


def initialise_embedded_fields_on_view_model(
    cls: type[RootNode] | type[ReifiedRelation],
):
    for embedded_field_definition in cls.field_definitions.embedded_fields:
        embedded_models = []
        for embedded_type in embedded_field_definition.field_concrete_types:
            if not getattr(embedded_type, "EmbeddedView", None):
                embedded_type.EmbeddedView = create_embedded_view_model(embedded_type)
            embedded_models.append(embedded_type.EmbeddedView)

        cls.View.model_fields[embedded_field_definition.field_name] = (
            pydantic.fields.FieldInfo.from_annotation(
                list[
                    typing.Union[*embedded_models]  # type: ignore
                ]
            )
        )

        cls.View.model_fields[
            embedded_field_definition.field_name
        ].metadata = embedded_field_definition.validators
        cls.View.model_fields[
            embedded_field_definition.field_name
        ].discriminator = "type"


def initialise_view_type_for_base(cls: type[RootNode] | type[ReifiedRelation]):
    if getattr(cls, "View", None) and cls.View.generated:
        return

    if not getattr(cls, "View", None):
        cls.View = pydantic.create_model(
            f"{cls.__name__}View",
            __base__=ViewBase,
            generated=(typing.ClassVar[bool], True),
        )

    view_is_manual = not cls.View.generated

    # Add property fields
    for property_field_definition in cls.field_definitions.property_fields:
        cls.View.model_fields[property_field_definition.field_name] = (
            pydantic.fields.FieldInfo.from_annotation(
                property_field_definition.field_annotated_type,
            )
        )
        cls.View.model_fields[
            property_field_definition.field_name
        ].metadata = property_field_definition.validators

    initialise_relation_fields_on_view_model(cls)
    initialise_embedded_fields_on_view_model(cls)

    cls.View.base_class = cls
    cls.View.model_rebuild(force=True)


def recurse_embedded_models_for_all_outgoing_relation_field_definitions(
    source_class: type[RootNode],
) -> list[RelationFieldDefinition]:
    """Given a model, go through all embedded models to find the target of
    outgoing relations, and the relation name"""

    relation_definitions: list[RelationFieldDefinition] = []
    for relation_definition in source_class.field_definitions.relation_fields:
        relation_definitions.append(relation_definition)
    for embedded_definition in source_class.field_definitions.embedded_fields:
        for embedded_concrete_type in embedded_definition.field_concrete_types:
            relation_definitions.extend(
                recurse_embedded_models_for_all_outgoing_relation_field_definitions(
                    embedded_concrete_type
                )
            )
    return relation_definitions


def create_incoming_relation_definitions_from_model(source_class: type[RootNode]):
    for (
        outgoing_relation_definition
    ) in recurse_embedded_models_for_all_outgoing_relation_field_definitions(
        source_class
    ):
        for concrete_target_class in outgoing_relation_definition.field_concrete_types:
            if (
                issubclass(concrete_target_class, RootNode)
                and outgoing_relation_definition.relation_model
            ):
                concrete_target_class.incoming_relation_definitions[
                    outgoing_relation_definition.reverse_name
                ].add(
                    IncomingRelationDefinition(
                        field_name=outgoing_relation_definition.field_name,
                        reverse_name=outgoing_relation_definition.reverse_name,
                        source_type=source_class,
                        source_concrete_type=create_reference_view_model_with_property_model(
                            origin_model=source_class,
                            target_model=concrete_target_class,
                            relation_model=outgoing_relation_definition.relation_model,
                            field_name=outgoing_relation_definition.field_name,
                        ),
                        target_type=concrete_target_class,
                    )
                )

            elif issubclass(concrete_target_class, RootNode):
                concrete_target_class.incoming_relation_definitions[
                    outgoing_relation_definition.reverse_name
                ].add(
                    IncomingRelationDefinition(
                        field_name=outgoing_relation_definition.field_name,
                        reverse_name=outgoing_relation_definition.reverse_name,
                        source_type=source_class,
                        source_concrete_type=source_class.ReferenceView,
                        target_type=concrete_target_class,
                    )
                )
            elif issubclass(concrete_target_class, ReifiedRelation):
                initialise_reified_relation(concrete_target_class)

                paths_to_target_node = get_paths_to_target_node(
                    concrete_target_class, outgoing_relation_definition
                )

                for path in paths_to_target_node:
                    target_class, to_target_relation_definition = path.target

                    # If the "target" class is bound to a reified relation as the direct
                    # target, add an inside-out reverse definition model
                    if to_target_relation_definition.field_name == "target":
                        add_reverse_definition_through_reified_relation_model_to_target(
                            path, source_class, outgoing_relation_definition
                        )

                    # Otherwise, if it is bound as a secondary relation to a reified relation,
                    # just add the whole relation chain
                    else:
                        print("====")
                        print(target_class)
                        print(to_target_relation_definition.field_name)
                        add_reverse_pointer_to_reified_relation(
                            source_class=source_class,
                            target_class=target_class,
                            outgoing_relation_definition=outgoing_relation_definition,
                            to_target_relation_definition=to_target_relation_definition,
                            reified_relation_model=concrete_target_class,
                        )


def add_reverse_pointer_to_reified_relation(
    source_class: type[RootNode],
    target_class: type[RootNode],
    outgoing_relation_definition: "RelationFieldDefinition",
    to_target_relation_definition: "RelationFieldDefinition",
    reified_relation_model: type[ReifiedRelation],
):
    """Builds and adds an incoming relation to a model when it is referenced
    by a refied relation."""

    # The starting model is a ReferenceView type, that contains in addition
    # the particular reified relation field
    starting_model = pydantic.create_model(
        f"{source_class.__name__}With{reified_relation_model.__name__}",
        __base__=source_class.ReferenceView,
    )

    starting_model.model_fields[outgoing_relation_definition.field_name] = (
        source_class.model_fields[outgoing_relation_definition.field_name]
    )
    starting_model.model_rebuild(force=True)

    target_class.incoming_relation_definitions[
        to_target_relation_definition.reverse_name
    ].add(
        IncomingRelationDefinition(
            field_name=to_target_relation_definition.field_name,
            reverse_name=to_target_relation_definition.reverse_name,
            source_type=reified_relation_model,
            source_concrete_type=ReifiedRelationNonTargetPointer[starting_model],
            target_type=target_class,
        )
    )


def add_reverse_definition_through_reified_relation_model_to_target(
    path: PathToTargetRootNode,
    source_model: type[RootNode],
    initial_relation_definition: "RelationFieldDefinition",
):
    """Builds and adds an incoming relation to a model when it is the target
    of a reified relation"""

    target, to_target_relation_definition = path.target

    # THIS is what we need to set
    # target.incoming_relation_definitions[relation_definition.reverse_name]

    # _, last_relation_definition = path.path_items[-1]

    current_innermost_class = source_model.ReferenceView

    path.path_items.reverse()
    key = None

    while path.path_items:
        next_wrapping_model, next_relation_definition = path.path_items.pop()
        if not key:
            key = next_relation_definition.reverse_name
        new_wrapping_model = pydantic.create_model(
            f"{next_wrapping_model.__name__}__ReverseView",
            __base__=next_wrapping_model,
            is_target_of=(current_innermost_class, ...),
            uuid=(uuid.UUID, ...),
        )
        del new_wrapping_model.model_fields["target"]
        next_wrapping_model.model_rebuild(force=True)
        current_innermost_class = new_wrapping_model

    target.incoming_relation_definitions[initial_relation_definition.reverse_name].add(
        IncomingRelationDefinition(
            field_name=initial_relation_definition.field_name,
            reverse_name=initial_relation_definition.reverse_name,
            source_type=source_model,
            source_concrete_type=current_innermost_class,
            target_type=target,
        )
    )
