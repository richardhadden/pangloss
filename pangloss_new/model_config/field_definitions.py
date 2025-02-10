import dataclasses
import datetime
import enum
import types
import typing

import annotated_types

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.models_base import (
        EdgeModel,
        HeritableTrait,
        MultiKeyField,
        NonHeritableTrait,
        ReifiedRelation,
        RootNode,
    )


@dataclasses.dataclass
class FieldDefinition:
    field_name: str


type MappedCypherTypes = (
    bool
    | int
    | float
    | str
    | datetime.date
    | datetime.timedelta
    | datetime.datetime
    | enum.Enum
)


@dataclasses.dataclass
class PropertyFieldDefinition(FieldDefinition):
    field_annotation: type[MappedCypherTypes]
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    field_metatype: typing.Literal["PropertyField"] = "PropertyField"


@dataclasses.dataclass
class MultiKeyFieldDefinition(PropertyFieldDefinition):
    field_annotation: type["MultiKeyField[MappedCypherTypes]"]
    field_metatype: typing.Literal["MultiKeyField"] = "MultiKeyField"


@dataclasses.dataclass
class ListFieldDefinition(FieldDefinition):
    field_annotation: type[MappedCypherTypes]
    field_metatype: typing.Literal["ListField"] = "ListField"
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )


@dataclasses.dataclass
class EmbeddedFieldDefinition(FieldDefinition):
    field_annotation: type["RootNode"] | types.UnionType
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    field_metatype: typing.Literal["EmbeddedField"] = "EmbeddedField"
    field_concrete_types: typing.Iterable[type["RootNode"]] = dataclasses.field(
        default_factory=set
    )

    def __post_init__(self):
        if not self.validators:
            self.validators = [annotated_types.MinLen(1), annotated_types.MaxLen(1)]


@dataclasses.dataclass
class RelationDefinition:
    annotated_type: type["RootNode"]


@dataclasses.dataclass
class TypeParamsToTypeMap:
    type_param: typing.TypeVar | typing.ParamSpec | typing.TypeVarTuple
    type: type["RootNode"] | type["ReifiedRelation"]


@dataclasses.dataclass
class RelationToReifiedDefinition(RelationDefinition):
    annotated_type: type["ReifiedRelation"]
    origin_type: type["ReifiedRelation"]
    type_params_to_type_map: dict[
        str,
        TypeParamsToTypeMap,
    ]


@dataclasses.dataclass
class RelationFieldDefinition(FieldDefinition):
    field_annotation: (
        type["RootNode"]
        | types.UnionType
        | type["HeritableTrait"]
        | type["NonHeritableTrait"]
        | type["ReifiedRelation"]
    )
    reverse_name: str

    field_type_definitions: list[RelationDefinition | RelationToReifiedDefinition] = (
        dataclasses.field(default_factory=list)
    )

    edge_model: typing.Optional[type["EdgeModel"]] = None
    subclasses_relation: typing.Optional[str] = None

    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )

    field_metatype: typing.Literal["RelationField"] = "RelationField"
    relation_labels: set[str] = dataclasses.field(default_factory=set)
    reverse_relation_labels: set[str] = dataclasses.field(default_factory=set)
    default_type: typing.Optional[str] = None


@dataclasses.dataclass
class FieldSubset[T]:
    fields: dict[str, T] = dataclasses.field(default_factory=dict)

    def __getitem__(self, key) -> T | None:
        return self.fields[key]

    def __contains__(self, key):
        return key in self.fields

    def __iter__(self) -> typing.Generator[T, None, None]:
        for field in self.fields.values():
            yield field


@dataclasses.dataclass
class ModelFieldDefinitions:
    fields: dict[str, FieldDefinition] = dataclasses.field(default_factory=dict)

    def __getitem__(self, key) -> FieldDefinition | None:
        return self.fields[key]

    def __setitem__(self, key, value):
        self.fields[key] = value

    def __contains__(self, key):
        return key in self.fields

    def __iter__(self) -> typing.Generator[FieldDefinition, None, None]:
        for field in self.fields.values():
            yield field

    @property
    def relation_fields(
        self,
    ) -> FieldSubset[RelationFieldDefinition]:
        items = {
            field_name: field
            for field_name, field in self.fields.items()
            if isinstance(field, RelationFieldDefinition)
        }

        return FieldSubset[RelationFieldDefinition](fields=items)

    @property
    def embedded_fields(self) -> FieldSubset[EmbeddedFieldDefinition]:
        items = {
            field_name: field
            for field_name, field in self.fields.items()
            if isinstance(field, EmbeddedFieldDefinition)
        }

        return FieldSubset[EmbeddedFieldDefinition](fields=items)

    @property
    def property_fields(
        self,
    ) -> FieldSubset[
        PropertyFieldDefinition | ListFieldDefinition | MultiKeyFieldDefinition,
    ]:
        items = {
            field_name: field
            for field_name, field in self.fields.items()
            if isinstance(
                field,
                (PropertyFieldDefinition, ListFieldDefinition, MultiKeyFieldDefinition),
            )
        }

        return FieldSubset[
            PropertyFieldDefinition | ListFieldDefinition | MultiKeyFieldDefinition
        ](items)
