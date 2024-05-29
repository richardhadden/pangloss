import dataclasses
import inspect
import types
import typing

import pydantic

from pangloss.exceptions import PanglossConfigError
from pangloss.model_config.field_definitions import (
    ModelFieldDefinitions,
    FieldDefinition,
    LiteralFieldDefinition,
    ListFieldDefinition,
    EmbeddedFieldDefinition,
    RelationFieldDefinition,
)
from pangloss.model_config.models_base import (
    RootNode,
    Embedded,
    RelationConfig,
    ReifiedRelation,
    HeritableTrait,
    NonHeritableTrait,
)
from pangloss.model_config.model_setup_utils import (
    get_non_heritable_traits_as_indirect_ancestors,
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


def is_relation_field(
    type_origin,
    field_annotation,
    field_metadata,
    field_name: str,
    model: type["RootNode"],
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
    model: type[RootNode], field_name: str, field: pydantic.fields.FieldInfo
) -> FieldDefinition:
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


def initialise_model_field_definitions(cls: type[RootNode]):
    """Creates a model field_definition object for each field
    of a model"""
    cls.field_definitions = ModelFieldDefinitions()
    for field_name, field in cls.model_fields.items():
        cls.field_definitions[field_name] = build_field_definition_from_annotation(
            model=cls, field_name=field_name, field=field
        )


def delete_indirect_non_heritable_trait_fields__(
    cls: type[RootNode],
) -> None:
    trait_fields_to_delete = set()
    for trait in get_non_heritable_traits_as_indirect_ancestors(cls):
        for field_name in cls.model_fields:
            # AND AND... not in the parent class annotations that is *not* a trait...
            if field_name in trait.__annotations__ and trait not in cls.__annotations__:
                trait_fields_to_delete.add(field_name)
    for td in trait_fields_to_delete:
        del cls.model_fields[td]
