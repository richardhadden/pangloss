from __future__ import annotations

import dataclasses
import typing
import uuid
from collections import ChainMap

import annotated_types
import humps
from pydantic import BaseModel, ConfigDict, HttpUrl

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.field_definitions import ModelFieldDefinitions

STANDARD_MODEL_CONFIG: ConfigDict = {
    "alias_generator": humps.camelize,
    "populate_by_name": True,
    "use_enum_values": True,
    "arbitrary_types_allowed": True,
}


class EdgeModel(BaseModel):
    show_in_reverse_relation: typing.ClassVar[bool] = False
    model_config = STANDARD_MODEL_CONFIG

    field_definitions_initialised: typing.ClassVar[bool]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]

    @classmethod
    def __pydantic_init_subclass__(cls) -> None:
        pass


class _BaseClassProxy:
    __pg_base_class__: typing.ClassVar[type[RootNode]]

    @property
    def __pg_field_definitions__(self):
        return self.__pg_base_class__.__pg_field_definitions__


class RootNode:
    """Base class for basic BaseModel"""

    type: str

    Create: typing.ClassVar[type[CreateBase]]
    HeadView: typing.ClassVar[type[HeadViewBase]]
    View: typing.ClassVar[type[ViewBase]]
    EditHeadView: typing.ClassVar[type[EditHeadViewBase]]
    EditView: typing.ClassVar[type[EditViewBase]]
    EditSet: typing.ClassVar[type[EditSetBase]]
    ReferenceView: typing.ClassVar[type[ReferenceViewBase]]
    ReferenceSet: typing.ClassVar[type[ReferenceViewBase]]
    EmbeddedCreate: typing.ClassVar[type[EmbeddedCreateBase]]
    EmbeddedView: typing.ClassVar[type[EmbeddedViewBase]]
    EmbeddedSet: typing.ClassVar[type[EmbeddedSetBase]]

    __pg_annotations__: typing.ClassVar[ChainMap[str, type]]
    __pg_field_definitions__: typing.ClassVar["ModelFieldDefinitions"]

    class edit:
        __pg_base_class__: typing.ClassVar[type[RootNode]]

        @classmethod
        def get(cls, uuid: uuid.UUID | HttpUrl) -> EditHeadViewBase:
            # TODO: Sketching API so far
            return cls.__pg_base_class__.EditHeadView()

        def __new__(cls, *args, **kwargs) -> EditSetBase:
            # TODO: Sketching API so far
            return cls.__pg_base_class__.EditSet(*args, **kwargs)

    class view:
        __pg_base_class__: typing.ClassVar[type[RootNode]]

        @classmethod
        def get(cls, id: uuid.UUID | HttpUrl):
            # TODO: Sketching API so far
            pass

    def __init_subclass__(cls):
        from pangloss_new.model_config.model_manager import ModelManager

        ModelManager.register_base_model(cls)


class CreateBase(BaseModel):
    # id: No ID required as we are creating

    label: str


class EditViewBase(BaseModel):
    """Base model returned by API for editing"""

    pass


class EditHeadViewBase(EditViewBase):
    """Head Base model returned by API for editing (contains additional metadata)"""

    pass


class EditSetBase(BaseModel):
    """Base model for updates Post-ed to API"""


class ViewBase(BaseModel):
    """Base model returned by API for viewing; contains all fields"""

    type: str
    id: uuid.UUID
    label: str


class HeadViewBase(ViewBase):
    """Base model returned by API for viewing; includes reverse relatinos and additional metadata"""

    type: str
    id: uuid.UUID


class ReferenceViewBase(BaseModel):
    """Base model for viewing a Reference to an entity"""

    type: str
    id: uuid.UUID
    label: str


class ReferenceSetBase(BaseModel):
    """Base model for setting a Reference to an entity"""

    type: str
    id: uuid.UUID | HttpUrl


class ReifiedBase(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    Create: typing.ClassVar[type[CreateBase]]

    __pg_annotations__: typing.ClassVar[ChainMap[str, type]]


class ReifiedRelation[T](ReifiedBase):
    """Base model for creating a reified relation"""

    type: str
    target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]

    def __init_subclass__(cls) -> None:
        from pangloss_new.model_config.model_manager import ModelManager

        # Dubious hack to update the parameters used by typing module to allow
        # inheriting class to include additional type parameters
        cls.__parameters__ = cls.__type_params__

        ModelManager.register_reified_relation_model(cls)


class ReifiedRelationViewBase(BaseModel):
    """Base model for viewing a reified relation (contains uuid and additional metadata)"""

    type: str
    uuid: uuid.UUID
    head_uuid: typing.Optional[uuid.UUID] = None
    head_type: typing.Optional[str] = None


class Embedded[T]:
    embedded_type: T


class EmbeddedCreateBase(BaseModel):
    """Base model for creating an embedded node (same as RootNode without id)"""

    type: str


class EmbeddedViewBase(BaseModel):
    """Base model for viewing an embedded model"""

    type: str
    uuid: uuid.UUID
    head_uuid: typing.Optional[uuid.UUID] = None
    head_type: typing.Optional[str] = None


class EmbeddedSetBase(BaseModel):
    type: str
    uuid: uuid.UUID


class Trait:
    pass


class HeritableTrait(Trait):
    pass


class NonHeritableTrait(Trait):
    pass


class MultiKeyField[T](BaseModel):
    """Define a field with multiple additional fields.

    The main field type is supplied by the type param T and is assigned to the `value` field.
    Additional fields may be defined on the subclassed model."""

    value: T

    __pg_field_definitions__: typing.ClassVar["ModelFieldDefinitions"]


@dataclasses.dataclass
class RelationConfig:
    reverse_name: str
    subclasses_relation: typing.Optional[list[str] | frozenset[str]] = None
    edge_model: typing.Optional[type["EdgeModel"]] = None
    validators: list[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )

    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False
    default_type: typing.Optional[str] = None

    def __hash__(self):
        if self.subclasses_relation:
            self.subclasses_relation = frozenset(self.subclasses_relation)
        return hash(self.__dict__)
