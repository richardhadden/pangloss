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
    field_metatype: typing.ClassVar[
        typing.Literal["Field"]
        | typing.Literal["PropertyField"]
        | typing.Literal["MultiKeyField"]
        | typing.Literal["ListField"]
        | typing.Literal["EmbeddedField"]
        | typing.Literal["RelationField"]
    ]


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
    field_metatype: typing.ClassVar[typing.Literal["PropertyField"]] = "PropertyField"


@dataclasses.dataclass
class MultiKeyFieldDefinition(FieldDefinition):
    field_annotation: type["MultiKeyField[MappedCypherTypes]"]
    multi_key_field_type: type["MultiKeyField"]
    multi_key_field_value_type: typing.Any
    field_metatype: typing.ClassVar[typing.Literal["MultiKeyField"]] = "MultiKeyField"
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )


@dataclasses.dataclass
class ListFieldDefinition(FieldDefinition):
    field_annotation: type[MappedCypherTypes]
    field_metatype: typing.ClassVar[typing.Literal["ListField"]] = "ListField"
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    """Validators for the list type as a whole"""

    internal_type_validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    """Validators for each item in the list type"""


@dataclasses.dataclass
class EmbeddedFieldDefinition(FieldDefinition):
    field_annotation: type["RootNode"] | types.UnionType
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    field_metatype: typing.ClassVar[typing.Literal["EmbeddedField"]] = "EmbeddedField"
    field_concrete_types: typing.Iterable[type["RootNode"]] = dataclasses.field(
        default_factory=set
    )

    def __post_init__(self):
        if not self.validators:
            self.validators = [annotated_types.MinLen(1), annotated_types.MaxLen(1)]


@dataclasses.dataclass
class RelationDefinition:
    metatype: typing.ClassVar[typing.Literal["Relation"]] = "Relation"


@dataclasses.dataclass
class RelationToNodeDefinition(RelationDefinition):
    annotated_type: type["RootNode"]
    metatype: typing.ClassVar[typing.Literal["RelationToNode"]] = "RelationToNode"


@dataclasses.dataclass
class RelationToTypeVarDefinition(RelationDefinition):
    annotated_type: typing.TypeVar
    typevar_name: str
    metatype: typing.ClassVar[typing.Literal["RelationToTypeVar"]] = "RelationToTypeVar"


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
    metatype: typing.ClassVar[typing.Literal["RelationToReified"]] = "RelationToReified"


type annotation_types = (
    type["RootNode"]
    | types.UnionType
    | type["HeritableTrait"]
    | type["NonHeritableTrait"]
    | type["ReifiedRelation"]
    | typing.TypeVar
)


@dataclasses.dataclass
class RelationFieldDefinition(FieldDefinition):
    field_annotation: annotation_types
    reverse_name: str

    field_type_definitions: list[RelationDefinition] = dataclasses.field(
        default_factory=list
    )

    edge_model: typing.Optional[type["EdgeModel"]] = None
    subclasses_relation: typing.Optional[str] = None

    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )

    field_metatype: typing.ClassVar[typing.Literal["RelationField"]] = "RelationField"
    relation_labels: set[str] = dataclasses.field(default_factory=set)
    reverse_relation_labels: set[str] = dataclasses.field(default_factory=set)
    default_type: typing.Optional[str] = None

    @property
    def relations_to_node(self) -> list[RelationToNodeDefinition]:
        return [
            relation
            for relation in self.field_type_definitions
            if isinstance(relation, RelationToNodeDefinition)
        ]

    @property
    def relations_to_reified(self) -> list[RelationToReifiedDefinition]:
        return [
            relation
            for relation in self.field_type_definitions
            if isinstance(relation, RelationToReifiedDefinition)
        ]

    @property
    def relations_to_typevar(self) -> list[RelationToTypeVarDefinition]:
        return [
            relation
            for relation in self.field_type_definitions
            if isinstance(relation, RelationToTypeVarDefinition)
        ]


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
        PropertyFieldDefinition | ListFieldDefinition | MultiKeyFieldDefinition
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
