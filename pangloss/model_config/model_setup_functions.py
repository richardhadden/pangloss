import collections
import copy
import dataclasses
import inspect
import types
import typing

import pydantic

from pangloss.exceptions import PanglossConfigError
from pangloss.model_config.field_definitions import (
    EmbeddedFieldDefinition,
    FieldDefinition,
    IncomingRelationDefinition,
    ListFieldDefinition,
    LiteralFieldDefinition,
    ModelFieldDefinitions,
    MultiKeyFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.model_manager import ModelManager
from pangloss.model_config.model_setup_utils import (
    create_reference_set_model_with_property_model,
    create_reference_view_model_with_property_model,
    get_non_heritable_mixins_as_direct_ancestors,
    get_non_heritable_traits_as_indirect_ancestors,
    get_paths_to_target_node,
    recurse_embedded_models_for_all_outgoing_relation_field_definitions,
)
from pangloss.model_config.models_base import (
    EdgeModel,
    EditSetBase,
    EditViewBase,
    Embedded,
    EmbeddedCreateBase,
    EmbeddedSetBase,
    EmbeddedViewBase,
    HeadViewBase,
    HeritableTrait,
    MultiKeyField,
    NonHeritableTrait,
    ReferenceSetBase,
    ReferenceViewBase,
    ReifiedRelation,
    ReifiedRelationNode,
    ReifiedRelationViewBase,
    RelationConfig,
    RootNode,
    ViewBase,
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
    model: type[RootNode]
    | type[ReifiedRelation]
    | type[ReferenceSetBase]
    | type[MultiKeyField]
    | type[EdgeModel]
    | type[ReferenceViewBase]
    | type[EmbeddedCreateBase]
    | type[ViewBase],
) -> bool:
    relation_config = get_relation_config_from_field_metadata(field_metadata)

    # If annotation type is a Union
    if (
        type_origin is types.UnionType or type_origin == typing.Union
    ) and relation_config:
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
    model: type[RootNode]
    | type[ReifiedRelation]
    | type[ReferenceSetBase]
    | type[MultiKeyField]
    | type[EdgeModel]
    | type[ReferenceViewBase]
    | type[EmbeddedCreateBase]
    | type[ViewBase],
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

    elif (
        field.annotation
        and inspect.isclass(field.annotation)
        and issubclass(field.annotation, MultiKeyField)
    ):
        return MultiKeyFieldDefinition(
            field_name=field_name,
            field_annotated_type=field.annotation,  # type: ignore
            validators=field.metadata,
        )

    elif field.annotation:
        return LiteralFieldDefinition(
            field_name=field_name,
            field_annotated_type=field.annotation,  # type: ignore
            validators=field.metadata,
        )

    raise Exception("Field type not caught")


def build_incoming_relation_definitions(source_class: type[RootNode]):
    # Add relation fields
    for (
        outgoing_relation_definition
    ) in recurse_embedded_models_for_all_outgoing_relation_field_definitions(
        source_class
    ):
        for concrete_target_class in outgoing_relation_definition.field_concrete_types:
            if (
                issubclass(concrete_target_class, RootNode)
                and outgoing_relation_definition.edge_model
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
                            edge_model=outgoing_relation_definition.edge_model,
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
                    if path.path_is_all_target:
                        # Flip path
                        path.path_items.reverse()

                        # If path is all target, attach using the reverse field name
                        # of the source class
                        target_node, to_target_definition = path.target

                        final_path_node, final_to_path_node_definition = (
                            path.path_items[-1]
                        )

                        reverse_name = final_to_path_node_definition.reverse_name
                        field_name = final_to_path_node_definition.field_name

                        if issubclass(source_class, ReifiedRelation) and not issubclass(
                            source_class, ReifiedRelationNode
                        ):
                            print(source_class)
                            source_concrete_class = pydantic.create_model(
                                f"{source_class.__name__}__from__{field_name}__{target_node.__name__}__View",
                                __base__=ReifiedRelationViewBase,
                                base_class=source_class,
                            )

                        else:
                            source_concrete_class = pydantic.create_model(
                                f"{source_class.__name__}__from__{field_name}__{target_node.__name__}__View",
                                __base__=ViewBase,
                                base_class=source_class,
                                field_definitions_initialised=(
                                    typing.ClassVar[bool],
                                    ...,
                                ),
                                field_definitions=(
                                    typing.ClassVar["ModelFieldDefinitions"],
                                    ...,
                                ),
                            )
                            source_concrete_class.field_definitions_initialised = False

                        source_concrete_class.model_fields[field_name] = (
                            source_class.View.model_fields[field_name]
                        )

                        if to_target_definition.edge_model:
                            source_concrete_class.model_fields["edge_properties"] = (
                                pydantic.fields.FieldInfo.from_annotation(
                                    to_target_definition.edge_model
                                )
                            )

                        source_concrete_class.model_rebuild(force=True)

                        target_node.incoming_relation_definitions[reverse_name].add(
                            IncomingRelationDefinition(
                                field_name=field_name,
                                reverse_name=reverse_name,
                                source_type=source_class,
                                source_concrete_type=source_concrete_class,
                                target_type=target_node,
                            )
                        )

                    else:
                        # It's at some intermediate point, so use the intermediate point
                        # name to bind
                        path.path_items.reverse()

                        # If path is all target, attach using the reverse field name
                        # of the source class
                        target_node, to_target_definition = path.target

                        field_name = ""
                        reverse_name = ""

                        for path_field_definition in [
                            to_target_definition,
                            *[path_item[1] for path_item in path.path_items],
                        ]:
                            if path_field_definition.field_name != "target":
                                field_name = path_field_definition.field_name
                                reverse_name = path_field_definition.reverse_name
                                break

                        if issubclass(source_class, ReifiedRelation) and not issubclass(
                            source_class, ReifiedRelationNode
                        ):
                            source_concrete_class = pydantic.create_model(
                                f"{source_class.__name__}__from__{field_name}__{target_node.__name__}__View",
                                __base__=ReifiedRelationViewBase,
                                base_class=source_class,
                            )

                        else:
                            source_concrete_class = pydantic.create_model(
                                f"{source_class.__name__}__from__{field_name}__{target_node.__name__}__View",
                                __base__=ViewBase,
                                base_class=source_class,
                            )

                        final_path_node, final_to_path_node_definition = (
                            path.path_items[-1]
                        )

                        final_field_name = field_name = (
                            final_to_path_node_definition.field_name
                        )

                        source_concrete_class.model_fields[final_field_name] = (
                            source_class.View.model_fields[final_field_name]
                        )

                        if to_target_definition.edge_model:
                            source_concrete_class.model_fields["edge_properties"] = (
                                pydantic.fields.FieldInfo.from_annotation(
                                    to_target_definition.edge_model
                                )
                            )

                        source_concrete_class.model_rebuild(force=True)

                        target_node.incoming_relation_definitions[reverse_name].add(
                            IncomingRelationDefinition(
                                field_name=field_name,
                                reverse_name=reverse_name,
                                source_type=source_class,
                                source_concrete_type=source_concrete_class,
                                target_type=target_node,
                            )
                        )


def initialise_model_field_definitions(
    cls: type[RootNode]
    | type[ReifiedRelation]
    | type[ReferenceSetBase]
    | type[EdgeModel]
    | type[MultiKeyField]
    | type[EmbeddedCreateBase]
    | type[ReferenceViewBase]
    | type[ViewBase],
):
    """Creates a model field_definition object for each field
    of a model"""

    if cls.field_definitions_initialised:
        return

    cls.field_definitions = ModelFieldDefinitions()
    for field_name, field in cls.model_fields.items():
        cls.field_definitions[field_name] = build_field_definition_from_annotation(
            model=cls, field_name=field_name, field=field
        )
    cls.field_definitions_initialised = True


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
        cls.__dict__.get("ReferenceSet", None)
        and inspect.isclass(cls.ReferenceSet)
        and issubclass(cls.ReferenceSet, ReferenceSetBase)
    ):
        cls.ReferenceSet.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore
        cls.ReferenceSet.model_fields["type"].default = cls.__name__
        cls.ReferenceSet.base_class = cls
        return

    # If ReferenceSet is manually defined but does not fulfil requirement above (subclassing
    # ReferenceViewSet), raise an error
    if cls.__dict__.get("ReferenceSet", None):
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
    initialise_model_field_definitions(cls.ReferenceSet)


def initialise_reference_view_on_base_models(cls: type[RootNode]):
    # If ReferenceView manually defined on a class, and it is a subclass
    # of ReferenceViewBase, just override the `type` field to the class name
    if (
        cls.__dict__.get("ReferenceView", None)
        and inspect.isclass(cls.ReferenceView)
        and issubclass(cls.ReferenceView, ReferenceViewBase)
    ):
        cls.ReferenceView.model_fields["type"].annotation = typing.Literal[cls.__name__]  # type: ignore
        cls.ReferenceView.model_fields["type"].default = cls.__name__
        cls.ReferenceView.base_class = cls
        return

    # If ReferenceView is manually defined but does not fulfil requirement above (subclassing
    # ReferenceViewBase), raise an error
    if cls.__dict__.get("ReferenceView", None):
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
                if field.create_inline and field.edge_model:
                    create_inline_model_with_edge_model = pydantic.create_model(
                        f"{cls.__name__}__{field.field_name}__{concrete_type.__name__}__CreateInline",
                        __base__=concrete_type,
                        edge_properties=(field.edge_model, ...),
                    )
                    reference_types.append(create_inline_model_with_edge_model)
                elif field.create_inline:
                    reference_types.append(concrete_type)
                elif field.edge_model:
                    reference_types.append(
                        create_reference_set_model_with_property_model(
                            origin_model=cls,
                            target_model=concrete_type,
                            edge_model=field.edge_model,
                            field_name=field.field_name,
                        )
                    )
                else:
                    reference_types.append(concrete_type.ReferenceSet)

            if issubclass(concrete_type, ReifiedRelation):
                if field.edge_model:
                    initialise_reified_relation(concrete_type)
                    reified_edge_model_with_relation_property_model = pydantic.create_model(
                        f"{cls.__name__}__{field.field_name}__{concrete_type.__name__}",
                        __base__=concrete_type,
                        edge_properties=(field.edge_model, ...),
                    )
                    reference_types.append(
                        reified_edge_model_with_relation_property_model
                    )
                else:
                    initialise_reified_relation(concrete_type)
                    reference_types.append(concrete_type)

        cls.model_fields[field.field_name].annotation = list[
            typing.Union[
                *reference_types  # type: ignore
            ]
        ]
        # cls.model_fields[field.field_name].discriminator = "type"

        cls.model_fields[field.field_name].metadata = field.validators


def create_embedded_create_model(cls: type[RootNode]) -> type[EmbeddedCreateBase]:
    embedded_create_model = pydantic.create_model(
        f"{cls.__name__}Embedded", __base__=EmbeddedCreateBase
    )
    embedded_create_model.base_class = cls

    for field_name, field in cls.model_fields.items():
        if field_name != "label":
            embedded_create_model.model_fields[field_name] = field

    embedded_create_model.model_rebuild(force=True)

    return embedded_create_model


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

    embedded_set_model.model_fields.update(fields)
    embedded_set_model.model_rebuild(force=True)

    # It should not be necessary to initialise anything on this model
    # as it inherits the already-initialised fields from its container base class

    return embedded_set_model


def create_embedded_view_model(cls: type[RootNode]):
    embedded_view_model = pydantic.create_model(
        f"{cls.__name__}EmbeddedView", __base__=EmbeddedViewBase
    )
    embedded_view_model.base_class = cls

    fields = {
        field_name: field
        for field_name, field in cls.model_fields.items()
        if field_name != "label"
    }

    embedded_view_model.model_fields.update(fields)

    for relation_definition in cls.field_definitions.relation_fields:
        concrete_types: list[
            type[ReferenceViewBase] | type[ReifiedRelationViewBase]
        ] = [
            m.ReferenceView
            for m in relation_definition.field_concrete_types
            if issubclass(m, RootNode)
        ]
        concrete_types.extend(
            [
                m.View
                for m in relation_definition.field_concrete_types
                if issubclass(m, ReifiedRelation)
            ]
        )
        if relation_definition.edge_model:
            concrete_types = [
                create_reference_view_model_with_property_model(
                    origin_model=cls,
                    target_model=concrete_type,
                    edge_model=relation_definition.edge_model,
                    field_name=relation_definition.field_name,
                )
                for concrete_type in concrete_types
            ]

        embedded_view_model.model_fields[relation_definition.field_name] = (
            pydantic.fields.FieldInfo.from_annotation(
                list[typing.Union[*concrete_types]]  # type: ignore
            )
        )

    embedded_view_model.model_rebuild(force=True)

    # It should not be necessary to initialise anything on this model
    # as it inherits the already-initialised fields from its container base class

    return embedded_view_model


def initialise_embedded_nodes_on_base_model(
    cls: type[RootNode] | type[ReifiedRelation],
):
    for embedded_field_definition in cls.field_definitions.embedded_fields:
        embedded_models = []
        for embedded_type in embedded_field_definition.field_concrete_types:
            if not getattr(embedded_type, "EmbeddedCreate", None):
                embedded_type.Embedded = create_embedded_create_model(embedded_type)
            embedded_models.append(embedded_type.Embedded)

        cls.model_fields[embedded_field_definition.field_name].annotation = list[
            typing.Union[*embedded_models]  # type: ignore
        ]
        cls.model_fields[
            embedded_field_definition.field_name
        ].metadata = embedded_field_definition.validators


def initialise_reified_relation(reified_relation: type[ReifiedRelation]):
    set_type_to_literal_on_base_model(reified_relation)
    initialise_model_field_definitions(reified_relation)
    initialise_outgoing_relation_types_on_base_model(reified_relation)


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
                    and relation_field_definition.edge_model
                ):
                    create_inline_model_with_edge_model = pydantic.create_model(
                        f"{cls.__name__}__{relation_field_definition.field_name}__{concrete_type.__name__}__ViewInline",
                        __base__=concrete_type.View,
                        edge_properties=(
                            relation_field_definition.edge_model,
                            ...,
                        ),
                    )
                    referenced_types.append(create_inline_model_with_edge_model)
                elif relation_field_definition.create_inline:
                    referenced_types.append(concrete_type.View)

                elif relation_field_definition.edge_model:
                    referenced_types.append(
                        create_reference_view_model_with_property_model(
                            origin_model=cls,
                            target_model=concrete_type,
                            edge_model=relation_field_definition.edge_model,
                            field_name=relation_field_definition.field_name,
                        )
                    )
                else:
                    referenced_types.append(concrete_type.ReferenceView)
            if issubclass(concrete_type, ReifiedRelation):
                initialise_view_type_for_base(concrete_type)
                if relation_field_definition.edge_model:
                    reified_relation_view_model_with_relation_property_model = pydantic.create_model(
                        f"{cls.__name__}__{relation_field_definition.field_name}__{concrete_type.__name__}__View",
                        __base__=concrete_type.View,
                        edge_properties=(
                            relation_field_definition.edge_model,
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
        """ cls.View.model_fields[
            embedded_field_definition.field_name
        ].discriminator = "type" """


def initialise_view_type_for_base(cls: type[RootNode] | type[ReifiedRelation]):
    if cls.__dict__.get("View", None) and cls.View.generated:
        return

    if not cls.__dict__.get("View", None):
        if issubclass(cls, ReifiedRelation) and not issubclass(
            cls, ReifiedRelationNode
        ):
            cls.View = pydantic.create_model(
                f"{cls.__name__}View",
                __base__=ReifiedRelationViewBase,
                generated=(typing.ClassVar[bool], True),
            )
        else:
            cls.View = pydantic.create_model(
                f"{cls.__name__}View",
                __base__=ViewBase,
                generated=(typing.ClassVar[bool], True),
            )

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

    if issubclass(cls, RootNode):
        cls.HeadView = pydantic.create_model(
            f"{cls.__name__}HeadView", __base__=HeadViewBase
        )
        cls.HeadView.model_fields.update(cls.View.model_fields)
        cls.HeadView.model_rebuild(force=True)


def initialise_incoming_relations_on_view_types_for_base(cls: type[RootNode]):
    for (
        incoming_field_name,
        incoming_relation_definitions,
    ) in cls.incoming_relation_definitions.items():
        incoming_relation_types = []

        for incoming_relation_definition in incoming_relation_definitions:
            incoming_relation_types.append(
                incoming_relation_definition.source_concrete_type
            )

        cls.View.model_fields[incoming_field_name] = (
            pydantic.fields.FieldInfo.from_annotation(
                list[typing.Union[*incoming_relation_types]]  # type: ignore
            )
        )
        cls.View.model_fields[incoming_field_name].default_factory = list
        cls.View.model_rebuild(force=True)

        cls.HeadView.model_fields[incoming_field_name] = (
            pydantic.fields.FieldInfo.from_annotation(
                list[typing.Union[*incoming_relation_types]]  # type: ignore
            )
        )
        cls.HeadView.model_fields[incoming_field_name].default_factory = list
        cls.HeadView.model_rebuild(force=True)


def initialise_edit_view_type(cls: type[RootNode]):
    """Initialises EditView on a RootModel

    The cls.EditView should be the same as cls.View, without the incoming relations.
    To do this, we can just copy cls.View, as long as the incoming relations
    have not yet been initialised on the View class
    """
    cls.EditView = pydantic.create_model(
        f"{cls.__name__}EditView", __base__=EditViewBase
    )

    for k, v in copy.copy(cls.View.model_fields).items():
        cls.EditView.model_fields[k] = v
    cls.EditView.model_rebuild(force=True)
    cls.EditView.base_class = cls


def initialise_edit_set_type(
    cls: type[RootNode] | type[ReifiedRelation], omit_fields: list[str] | None = None
):
    if not omit_fields:
        omit_fields = []

    if not cls.__dict__.get("EditSet", None):
        cls.EditSet = pydantic.create_model(
            f"{cls.__name__}EditSet", __base__=EditSetBase
        )
        cls.EditSet.base_class = cls

    for property_field_definition in cls.field_definitions.property_fields:
        if property_field_definition.field_name in omit_fields:
            continue
        cls.EditSet.model_fields[property_field_definition.field_name] = (
            cls.model_fields[property_field_definition.field_name]
        )

    for relation_definition in cls.field_definitions.relation_fields:
        allowed_relation_types = collections.deque()

        for concrete_type in relation_definition.field_concrete_types:
            if issubclass(concrete_type, RootNode):
                if relation_definition.edit_inline:
                    if not concrete_type.__dict__.get("EditSet", None):
                        initialise_edit_set_type(concrete_type)
                    allowed_relation_types.append(
                        typing.Annotated[
                            concrete_type.EditSet,
                            pydantic.Tag("Existing_" + concrete_type.__name__),
                        ]
                    )
                    allowed_relation_types.append(
                        typing.Annotated[
                            concrete_type, pydantic.Tag("New_" + concrete_type.__name__)
                        ]
                    )
                else:
                    if relation_definition.edge_model:
                        reference_set_type = (
                            create_reference_set_model_with_property_model(
                                origin_model=cls,
                                target_model=concrete_type,
                                edge_model=relation_definition.edge_model,
                                field_name=relation_definition.field_name,
                            )
                        )
                        allowed_relation_types.append(
                            typing.Annotated[
                                reference_set_type,
                                pydantic.Tag("Reference_" + concrete_type.__name__),
                            ]
                        )
                    else:
                        allowed_relation_types.append(
                            typing.Annotated[
                                concrete_type.ReferenceSet,
                                pydantic.Tag("Reference_" + concrete_type.__name__),
                            ]
                        )

            if issubclass(concrete_type, ReifiedRelation):
                if not concrete_type.__dict__.get("EditSet", None):
                    initialise_edit_set_type(concrete_type)
                allowed_relation_types.appendleft(
                    typing.Annotated[
                        concrete_type.EditSet,
                        pydantic.Tag("Existing_" + concrete_type.__name__),
                    ]
                )
                allowed_relation_types.append(
                    typing.Annotated[
                        concrete_type, pydantic.Tag("New_" + concrete_type.__name__)
                    ]
                )

        def model_discriminator(v: typing.Any) -> str:
            is_dict = isinstance(v, dict)

            if (is_dict and not v.get("type", False)) and not hasattr(v, "type"):
                raise Exception("Type not provided in request")

            model_type = v.get("type") if is_dict else getattr(v, "type")
            if not isinstance(model_type, str):
                raise Exception("Type provided not a string")

            if not relation_definition.edit_inline:
                if model_type in ModelManager.registered_model_names:
                    return "Reference_" + model_type

            if (is_dict and v.get("uuid", None)) or hasattr(v, "uuid"):
                return "Existing_" + model_type

            return "New_" + model_type

        if allowed_relation_types:
            cls.EditSet.model_fields[relation_definition.field_name] = (
                pydantic.fields.FieldInfo.from_annotation(
                    list[
                        typing.Annotated[
                            typing.Union[*allowed_relation_types],  # type: ignore
                            pydantic.Field(
                                discriminator=pydantic.Discriminator(
                                    model_discriminator
                                ),
                            ),
                        ]
                    ],
                )
            )
        cls.EditSet.model_fields[
            relation_definition.field_name
        ].metadata = relation_definition.validators

    for embedded_definition in cls.field_definitions.embedded_fields:
        allowed_embedded_types = []
        for embedded_type in embedded_definition.field_concrete_types:
            # TODO: this embedded_type can't be the actual type;

            if not embedded_type.__dict__.get("EmbeddedSet", None):
                embedded_type.EmbeddedSet = create_embedded_set_model(embedded_type)

            allowed_embedded_types.append(
                typing.Annotated[
                    embedded_type.Embedded,
                    pydantic.Tag("New_" + embedded_type.__name__),
                ]
            )

            allowed_embedded_types.append(
                typing.Annotated[
                    embedded_type.EmbeddedSet,
                    pydantic.Tag("Existing_" + embedded_type.__name__),
                ]
            )

        def model_discriminator(v: typing.Any) -> str:
            is_dict = isinstance(v, dict)

            if (is_dict and not v.get("type", False)) and not hasattr(v, "type"):
                raise Exception("Type not provided in request")

            model_type = v.get("type") if is_dict else getattr(v, "type")
            if not isinstance(model_type, str):
                raise Exception("Type provided not a string")

            if (is_dict and v.get("uuid", None)) or hasattr(v, "uuid"):
                return "Existing_" + model_type

            return "New_" + model_type

        if allowed_embedded_types:
            cls.EditSet.model_fields[embedded_definition.field_name] = (
                pydantic.fields.FieldInfo.from_annotation(
                    list[
                        typing.Annotated[
                            typing.Union[*allowed_embedded_types],  # type: ignore
                            pydantic.Field(
                                discriminator=pydantic.Discriminator(
                                    model_discriminator
                                ),
                            ),
                        ]
                    ],
                )
            )

        cls.EditSet.model_fields[
            embedded_definition.field_name
        ].metadata = embedded_definition.validators

    cls.EditSet.model_rebuild(force=True)


def initialise_subclassed_relations(cls: type[RootNode]):
    """Identifies relation fields that override another inherited relation and
    removes the inherited relation field from the class, adding its relation-
    and reverse-relation labels to the field definition"""

    # to_delete = []
    for relation_definition in cls.field_definitions.relation_fields:
        if relation_definition.subclasses_relation:
            for subclassed_relation in relation_definition.subclasses_relation:
                # Check we are actually trying to subclass something that exists
                # on the class
                if subclassed_relation not in cls.model_fields:
                    raise PanglossConfigError(
                        f"Relation '{cls.__name__}.{relation_definition.field_name}' "
                        f"is trying to subclass the relation "
                        f"'{subclassed_relation}', but this "
                        f"does not exist on any parent class of '{cls.__name__}'"
                    )

                # If so, mark for deletion
                cls.subclassed_fields_to_delete.append(subclassed_relation)

                # Add the relation labels from the inherited field
                relation_definition.relation_labels.update(
                    cls.field_definitions[subclassed_relation].relation_labels  # type: ignore
                )

                # Add reverse relation labels from inherited field
                relation_definition.reverse_relation_labels.update(
                    typing.cast(
                        RelationFieldDefinition,
                        cls.field_definitions[subclassed_relation],
                    ).reverse_relation_labels
                )

                # Delete the subclassed relation from model fields

    # Remove all items from the field definition


def initialise_model_labels(cls: type[RootNode]) -> None:
    """All neo4j labels for model.

    Includes direct Trait names."""
    cls.labels = {
        c.__name__
        for c in cls.mro()
        if (
            (issubclass(c, (RootNode, HeritableTrait)))
            and c is not HeritableTrait
            or c in get_non_heritable_mixins_as_direct_ancestors(cls)
        )
        and c is not RootNode
    }
