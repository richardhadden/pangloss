import dataclasses
import datetime
import enum
import types
import typing

import annotated_types

from pangloss.model_config.models_base import (
    RootNode,
    RelationPropertiesModel,
    ReifiedRelation,
    HeritableTrait,
    NonHeritableTrait,
    IncomingRelationView,
    ReferenceViewBase,
)
from pangloss.model_config.model_setup_utils import get_concrete_model_types


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
MappedCypherTypesSet = set(
    [
        bool,
        int,
        float,
        str,
        datetime.date,
        datetime.timedelta,
        datetime.datetime,
        enum.Enum,
    ]
)


@dataclasses.dataclass
class LiteralFieldDefinition(FieldDefinition):
    field_annotated_type: type[MappedCypherTypes]
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    field_metatype: typing.Literal["Literal"] = "Literal"


@dataclasses.dataclass
class ListFieldDefinition(FieldDefinition):
    field_annotated_type: type[MappedCypherTypes]
    field_metatype: typing.Literal["List"] = "List"
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )


@dataclasses.dataclass
class EmbeddedFieldDefinition(FieldDefinition):
    field_annotated_type: type["RootNode"] | types.UnionType
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    field_metatype: typing.Literal["Embedded"] = "Embedded"
    field_concrete_types: typing.Iterable[type["RootNode"]] = dataclasses.field(
        default_factory=set
    )

    def __post_init__(self):
        self.field_concrete_types = get_concrete_model_types(self.field_annotated_type)
        print(self.field_concrete_types)
        if not self.validators:
            self.validators = [annotated_types.MinLen(1), annotated_types.MaxLen(1)]


@dataclasses.dataclass
class RelationFieldDefinition(FieldDefinition):
    field_annotated_type: (
        type["RootNode"]
        | types.UnionType
        | type["ReifiedRelation"]
        | type["HeritableTrait"]
        | type["NonHeritableTrait"]
    )

    reverse_name: str
    relation_model: typing.Optional[type["RelationPropertiesModel"]] = None
    subclasses_relation: typing.Optional[str] = None
    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    field_concrete_types: typing.Iterable[
        type["RootNode"] | type["ReifiedRelation"]
    ] = dataclasses.field(default_factory=set)
    field_metatype: typing.Literal["Relation"] = "Relation"

    def __post_init__(self):
        self.field_concrete_types = get_concrete_model_types(self.field_annotated_type)


@dataclasses.dataclass
class IncomingRelationDefinition(FieldDefinition):
    reverse_name: str
    source_type: type["RootNode"] | type["ReifiedRelation"]
    source_concrete_type: type["ReferenceViewBase"] | type["IncomingRelationView"]
    target_type: type["RootNode"]

    def __hash__(self):
        return hash(self.reverse_name + str(self.source_type) + str(self.target_type))


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
        for key, field in self.fields.items():
            yield field

    @property
    def relation_fields(
        self,
    ) -> typing.Generator[RelationFieldDefinition, None, None]:
        for key, field in self.fields.items():
            if isinstance(field, RelationFieldDefinition):
                yield field

    @property
    def embedded_fields(self) -> typing.Generator[EmbeddedFieldDefinition, None, None]:
        for key, field in self.fields.items():
            if isinstance(field, EmbeddedFieldDefinition):
                yield field

    @property
    def property_fields(
        self,
    ) -> typing.Generator[LiteralFieldDefinition | ListFieldDefinition, None, None]:
        for key, field in self.fields.items():
            if isinstance(field, (LiteralFieldDefinition, ListFieldDefinition)):
                yield field
