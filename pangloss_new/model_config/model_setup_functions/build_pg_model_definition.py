import dataclasses
import inspect
import types
import typing

import annotated_types

from pangloss_new.exceptions import PanglossConfigError
from pangloss_new.model_config.field_definitions import (
    EmbeddedFieldDefinition,
    FieldDefinition,
    ListFieldDefinition,
    ModelFieldDefinitions,
    MultiKeyFieldDefinition,
    PropertyFieldDefinition,
    RelationFieldDefinition,
    RelationToNodeDefinition,
    RelationToReifiedDefinition,
    RelationToTypeVarDefinition,
    TypeParamsToTypeMap,
)
from pangloss_new.model_config.models_base import (
    EdgeModel,
    EmbeddedCreateBase,
    MultiKeyField,
    ReferenceSetBase,
    ReferenceViewBase,
    ReifiedBase,
    ReifiedRelation,
    RelationConfig,
    RootNode,
    Trait,
    ViewBase,
)
from pangloss_new.models import Embedded


def get_relation_config_from_field_metadata(
    field_metadata: tuple[typing.Any], field_name: str, model: typing.Any
) -> RelationConfig:
    try:
        return [
            metadata_item
            for metadata_item in field_metadata
            if isinstance(metadata_item, RelationConfig)
        ][0]
    except IndexError:
        raise PanglossConfigError(
            f"Relation field {field_name} on model {model.__name__} is missing a RelationConfig object"
        )


def is_relation_field__(
    annotation,
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
    type_origin = typing.get_origin(annotation)

    field_annotation = typing.get_args(annotation)[0]

    relation_config = get_relation_config_from_field_metadata(
        typing.get_args(annotation)[1:], field_name=field_name, model=model
    )

    # If annotation type is a Union
    if (
        type_origin is types.UnionType or type_origin == typing.Union
    ) and relation_config:
        union_types = typing.get_args(field_annotation)

        # Check all args to Union are RootNode or ReifiedRelation subclasses
        if all(
            (inspect.isclass(t) and issubclass(t, (RootNode, ReifiedRelation, Trait)))
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
        and issubclass(field_annotation, (RootNode, Trait))
        and relation_config
    ):
        return True
    return False


def pg_is_subclass(
    cls: typing.Any, parent_classes: tuple[typing.Any, ...] | typing.Any
) -> bool:
    """Checks whether at least one parent_class is in cls.mro()

    Use instead of builtin issubclass, which does not seem to work
    on resolved typing.ForwardRef
    """
    if not isinstance(parent_classes, tuple):
        parent_classes = (parent_classes,)
    for parent_class in parent_classes:
        if not hasattr(cls, "mro"):
            continue
        if parent_class in cls.mro():
            return True
    return False


def resolve_forward_ref(cls: typing.Any):
    if not isinstance(cls, typing.ForwardRef):
        return cls
    for f in inspect.stack():
        if isinstance(cls, typing.ForwardRef):
            try:
                frame = f.frame
                resolved_cls = cls._evaluate(
                    globalns={
                        **frame.f_globals,
                    },
                    localns=frame.f_locals,
                    type_params=(),
                    recursive_guard=frozenset(),
                )
                return resolved_cls
            except NameError:
                pass
    raise NameError(f"Cannot find {cls}")


def build_relation_fields_definitions(
    field_name: str, annotation: typing.Any, model, primary_type
) -> list[RelationToNodeDefinition]:
    """Possible primary_types:

    RootNode -> [RelationDefinition] TICK
    Union[RootNode | ReifiedRelation[RootNode]] -> [RelationDefinition, ReifiedRelationDefinition] TICK
    ReifiedRelation[RootNode] -> [ReifiedRelationDefinition] TICK
    ReifiedRelation[Union[RootNode | ReifiedRelation]] -> ReifiedRelationDefinition
    """
    if isinstance(primary_type, typing.TypeVar):
        return [
            RelationToTypeVarDefinition(
                annotated_type=primary_type, typevar_name=primary_type.__name__
            )
        ]

    # If the primary type is a ReifiedRelation, it is a ReifiedRelation
    elif issubclass(primary_type, ReifiedRelation):
        possible_generic_type = typing.cast(
            type[ReifiedRelation], primary_type.__pydantic_generic_metadata__["origin"]
        )

        inner_types = primary_type.__pydantic_generic_metadata__["args"]
        inner_types = typing.cast(
            list[type[RootNode | ReifiedRelation]],
            [resolve_forward_ref(inner_type) for inner_type in inner_types],
        )

        type_param_to_types_map = {
            type_param.__name__: TypeParamsToTypeMap(type_param, real_type)
            for type_param, real_type in zip(
                possible_generic_type.__parameters__, inner_types
            )
        }

        return [
            RelationToReifiedDefinition(
                annotated_type=primary_type,
                origin_type=possible_generic_type,
                type_params_to_type_map=type_param_to_types_map,
            )
        ]

    # Check whether the Annotated[Type, ...] is to a related model
    elif pg_is_subclass(primary_type, (RootNode, Trait)):
        return [RelationToNodeDefinition(annotated_type=primary_type)]

    else:
        return []


def is_annotated(ann: typing.Any) -> bool:
    return typing.get_origin(ann) is typing.Annotated


def is_union(ann: typing.Any) -> bool:
    # Check if is a union type via various mechanisms:
    # - Union of RootNode and ReifiedRelation can only be checked by __origin__
    # - Union of other types using "|" syntax are instances of types.UnionType
    # - Union of other types using typing.Union are equal to typing.Union
    return (
        getattr(ann, "__origin__", None) is typing.Union
        or isinstance(ann, types.UnionType)
        or ann == typing.Union
    )


def build_field_definition(
    field_name: str,
    annotation: typing.Any,
    model: type[RootNode] | type[ReifiedBase] | type[EdgeModel],
) -> FieldDefinition:
    # Handle annotated types, normally indicative of a relation but not necessarily:
    # Annotated[RelatedType, RelationConfig] or Annotated[str, some_validator]

    if issubclass(model, (ReifiedBase, EdgeModel)):
        # ReifiedBase is already necessarily a pydantic.BaseModel, which interprets
        # the annotation as a string; so need to do the actual lookups of types on the model
        # and then can reconstruct the type back to the unadulterated Python format
        # i.e. typing.Annotated[<Type>, *<Metadata>]
        # so we can use the same code below
        primary_type = model.model_fields[field_name].annotation

        if metadata := model.model_fields[field_name].metadata:
            annotation = typing.Annotated[primary_type, *metadata]

    elif is_annotated(annotation):
        # If it is an annotation, unpack to get the primary type
        validators = []
        # Get the first argument from the Annotated: should be the actual type
        primary_type = typing.get_args(annotation)[0]

        # Resolve any forward refs if required
        primary_type = resolve_forward_ref(primary_type)

    else:
        annotation = resolve_forward_ref(annotation)

    if is_annotated(annotation) and isinstance(primary_type, typing.TypeVar):
        relation_fields_definitions = build_relation_fields_definitions(
            field_name=field_name,
            annotation=annotation,
            model=model,
            primary_type=primary_type,
        )

        relation_config = get_relation_config_from_field_metadata(
            typing.get_args(annotation)[1:], field_name=field_name, model=model
        )

        # Check the annotation for additional validators
        additional_validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]

        # Convert relation_config to dict for splat-unpacking below
        relation_config_dict = dataclasses.asdict(relation_config)

        # Update the validators in the relation_config_dict to include
        # additional_validators. n.b. must be done after converting to dict
        # as relation_config validators will have been turned to dict!
        relation_config_dict["validators"] = [
            *relation_config.validators,
            *additional_validators,
        ]

        field_definition = RelationFieldDefinition(
            field_name=field_name,
            field_annotation=primary_type,
            field_type_definitions=relation_fields_definitions,
            **relation_config_dict,
        )
        return field_definition

    if is_annotated(annotation) and is_union(primary_type):
        # Union can be of RootNode/ReifiedRelation type or literal
        # If literal, raise error

        union_types = typing.get_args(primary_type)

        if not all(
            pg_is_subclass(t, (RootNode, Trait, ReifiedRelation)) for t in union_types
        ):
            raise PanglossConfigError(
                f"{field_name} on {model.__name__} contains a mix of relations"
                " and literal value types, or a mix of literal value types"
            )

        relation_fields_definitions = []
        for union_type in union_types:
            relation_fields_definitions.extend(
                build_relation_fields_definitions(
                    field_name=field_name,
                    annotation=annotation,
                    model=model,
                    primary_type=union_type,
                )
            )

        relation_config = get_relation_config_from_field_metadata(
            typing.get_args(annotation)[1:], field_name=field_name, model=model
        )

        # Check the annotation for additional validators
        additional_validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]

        # Convert relation_config to dict for splat-unpacking below
        relation_config_dict = dataclasses.asdict(relation_config)

        # Update the validators in the relation_config_dict to include
        # additional_validators. n.b. must be done after converting to dict
        # as relation_config validators will have been turned to dict!
        relation_config_dict["validators"] = [
            *relation_config.validators,
            *additional_validators,
        ]

        field_definition = RelationFieldDefinition(
            field_name=field_name,
            field_annotation=typing.cast(type[RootNode], primary_type),
            field_type_definitions=relation_fields_definitions,
            **relation_config_dict,
        )

        return field_definition

    if is_annotated(annotation) and pg_is_subclass(
        primary_type, (RootNode, ReifiedRelation, Trait)
    ):
        # If primary type is one class, build relation_definition here and get
        # relation fields definitions
        relation_fields_definitions = build_relation_fields_definitions(
            field_name=field_name,
            annotation=annotation,
            model=model,
            primary_type=primary_type,
        )
        # Get the RelationConfig instance from annotation
        relation_config = get_relation_config_from_field_metadata(
            typing.get_args(annotation)[1:], field_name=field_name, model=model
        )

        # Check the annotation for additional validators
        additional_validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]

        # Convert relation_config to dict for splat-unpacking below
        relation_config_dict = dataclasses.asdict(relation_config)

        # Update the validators in the relation_config_dict to include
        # additional_validators. n.b. must be done after converting to dict
        # as relation_config validators will have been turned to dict!
        relation_config_dict["validators"] = [
            *relation_config.validators,
            *additional_validators,
        ]

        field_definition = RelationFieldDefinition(
            field_name=field_name,
            field_annotation=typing.cast(type[RootNode], primary_type),
            field_type_definitions=relation_fields_definitions,
            **relation_config_dict,
        )

        return field_definition

    if (
        is_annotated(annotation)
        and typing.get_origin(primary_type) is list
        and is_annotated(typing.get_args(primary_type)[0])
    ):
        # Annotation of list and inner type, e.g.
        # Annotated[list[Annotated[str, MaxLen(10)]], MaxLen(2)]

        inner_type = typing.get_args(typing.get_args(primary_type)[0])[0]
        validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]
        internal_type_validators = [
            metadata_item
            for metadata_item in typing.get_args(typing.get_args(primary_type)[0])
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]
        return ListFieldDefinition(
            field_name=field_name,
            field_annotation=inner_type,
            field_metatype="ListField",
            validators=validators,
            internal_type_validators=internal_type_validators,
        )

    if is_annotated(annotation) and typing.get_origin(primary_type) is list:
        # Annotation of list type
        # Annotated[list[str], MaxLen(2)]
        validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]
        return ListFieldDefinition(
            field_name=field_name,
            field_annotation=typing.get_args(primary_type)[0],
            field_metatype="ListField",
            validators=validators,
        )

    if (
        is_annotated(annotation)
        and typing.get_origin(typing.get_args(annotation)[0]) is Embedded
    ):
        inner_type = typing.get_args(typing.get_args(annotation)[0])[0]
        inner_type = resolve_forward_ref(inner_type)
        inner_type = typing.cast(type[RootNode], inner_type)
        validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]
        return EmbeddedFieldDefinition(
            field_name=field_name,
            field_annotation=inner_type,
            validators=validators,
        )

    if is_annotated(annotation) and primary_type:
        # Annotation of base property type
        # e.g. Annotated[str, MaxLen(10)]

        validators = [
            metadata_item
            for metadata_item in typing.get_args(annotation)
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]

        return PropertyFieldDefinition(
            field_name=field_name,
            field_annotation=primary_type,
            validators=validators,
        )
    if typing.get_origin(annotation) is list and is_annotated(
        typing.get_args(annotation)[0]
    ):
        # List of annotated type
        # e.g. list[typing.Annotated[str, annotated_types.MaxLen(1)]]

        internal_type_validators = [
            metadata_item
            for metadata_item in typing.get_args(typing.get_args(annotation)[0])
            if isinstance(metadata_item, annotated_types.BaseMetadata)
        ]
        return ListFieldDefinition(
            field_name=field_name,
            field_annotation=typing.get_args(typing.get_args(annotation)[0])[0],
            internal_type_validators=internal_type_validators,
        )

    if typing.get_origin(annotation) is Embedded and is_union(
        inner_type := resolve_forward_ref(typing.get_args(annotation)[0])
    ):
        if not all(
            pg_is_subclass(t, (RootNode, Trait)) for t in typing.get_args(inner_type)
        ):
            raise PanglossConfigError(
                f"{model.__name__} {field_name}: cannot embed a literal typing, only subclass of BaseNode"
            )

        inner_type = typing.cast(types.UnionType, inner_type)

        return EmbeddedFieldDefinition(
            field_name=field_name, field_annotation=inner_type
        )

    if typing.get_origin(annotation) is Embedded:
        inner_type = resolve_forward_ref(typing.get_args(annotation)[0])
        if not pg_is_subclass(inner_type, (RootNode,)):
            raise PanglossConfigError(
                f"{model.__name__} {field_name}: cannot embed a literal type, only subclass of BaseNode"
            )
        inner_type = typing.cast(type[RootNode], inner_type)
        return EmbeddedFieldDefinition(
            field_name=field_name, field_annotation=inner_type
        )

    if typing.get_origin(annotation) is list:
        # List of base property type
        # e.g. list[str]
        return ListFieldDefinition(
            field_name=field_name,
            field_annotation=typing.get_args(annotation)[0],
            field_metatype="ListField",
        )

    if inspect.isclass(annotation) and issubclass(annotation, MultiKeyField):
        multi_key_field_type = typing.cast(
            type[MultiKeyField], annotation.__pydantic_generic_metadata__["origin"]
        )
        multi_key_field_value_type = annotation.__pydantic_generic_metadata__["args"][0]

        return MultiKeyFieldDefinition(
            field_name=field_name,
            field_annotation=annotation,
            multi_key_field_type=multi_key_field_type,
            multi_key_field_value_type=multi_key_field_value_type,
        )

    # Finally, any base annotation value
    # e.g. str
    return PropertyFieldDefinition(
        field_name=field_name,
        field_annotation=annotation,
    )


def build_pg_model_definitions(
    cls: type["RootNode"] | type["ReifiedBase"] | type["EdgeModel"],
) -> None:
    defs = {}
    for field_name, annotation in cls.__pg_annotations__.items():
        defs[field_name] = build_field_definition(field_name, annotation, model=cls)

    cls.__pg_field_definitions__ = ModelFieldDefinitions(defs)
