from __future__ import annotations

import dataclasses
import datetime
import typing
import uuid

import annotated_types
import humps
import pydantic

if typing.TYPE_CHECKING:
    from field_definitions import ModelFieldDefinitions

"""
Required model variations:

- Create:
    - No UUID, created_when, created_by, modified_when, modified_by (set by database)

- View:
    - Should return UUID, created_when, created_by, modified_when, modified_by
    - Should return reverse_relations
    
- Edit:
    - View: same as View but no reverse relations; related CreateInline/EditInline nodes should have Existant types only (EditView)
    - Set: same as EditGet; CreateInline/EditInline nodes take either EditView (existing) or Create (model itself)
    
- ReferenceView:
    - Is the result returned by API as list or when selected: returns type, uuid and label (separately overridable from )
    
- ReferenceSet:
    - Is the reference for selecting/returning a direct relation; needs type and uuid   
    
"""


class _SubNodeProxy:
    base_class: typing.ClassVar[type["RootNode"]]


STANDARD_MODEL_CONFIG: pydantic.ConfigDict = {
    "alias_generator": humps.camelize,
    "populate_by_name": True,
    "use_enum_values": True,
}


class _GenericNode(pydantic.BaseModel):
    type: str
    label: str

    model_config = {
        "alias_generator": humps.camelize,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class _ExtantNodeMixin:
    """Contains the fields that a model will have once it is created"""

    uuid: uuid.UUID
    created_when: datetime.datetime
    created_by: str
    modified_when: datetime.datetime
    modified_by: str
    is_deleted: bool = False


class ReifiedRelation[T](pydantic.BaseModel):
    target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]

    field_definitions: typing.ClassVar["ModelFieldDefinitions"]


class EditViewBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for getting model to edit"""

    pass


class EditSetBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for inputting edited model"""

    pass


class ViewBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for viewing model"""

    pass


# Reference types need to be separated, so that additional fields for viewing
# can be added for list-views, etc., while still only requiring necessary fields
# (type and uuid) for setting relations


class ReferenceViewBase(_GenericNode, _SubNodeProxy):
    """Base model for viewing reference to a model

    Requires uuid, type and label
    """

    uuid: uuid.UUID

    model_config = STANDARD_MODEL_CONFIG


class ReferenceSetBase(pydantic.BaseModel, _SubNodeProxy):
    """Base model for setting reference to a model

    Requires only the type of the model and the uuid
    """

    type: str
    uuid: uuid.UUID

    model_config = STANDARD_MODEL_CONFIG

    def _as_dict(self):
        return {"type": self.type, "uuid": self.uuid}


class EmbeddedSetBase(pydantic.BaseModel, _SubNodeProxy):
    @property
    def field_definitions(self) -> "ModelFieldDefinitions":
        return self.base_class.field_definitions


class EmbeddedViewBase(pydantic.BaseModel, _SubNodeProxy):
    type: str
    uuid: uuid.UUID


class RootNode(_GenericNode):
    """Default base model on creation"""

    View: typing.ClassVar[type[ViewBase]]
    EditView: typing.ClassVar[type[EditViewBase]]
    EditSet: typing.ClassVar[type[EditSetBase]]
    ReferenceView: typing.ClassVar[type[ReferenceViewBase]]
    ReferenceSet: typing.ClassVar[type[ReferenceSetBase]]
    EmbeddedSet: typing.ClassVar[type[EmbeddedSetBase]]
    EmbeddedView: typing.ClassVar[type[EmbeddedViewBase]]

    field_definitions: typing.ClassVar["ModelFieldDefinitions"]

    __abstract__: typing.ClassVar[bool] = True


class HeritableTrait:
    pass


class NonHeritableTrait:
    pass


class Embedded[T]:
    pass


class RelationPropertiesModel(pydantic.BaseModel):
    model_config = STANDARD_MODEL_CONFIG


@dataclasses.dataclass
class RelationConfig:
    reverse_name: str
    relation_model: typing.Optional[type["RelationPropertiesModel"]] = None
    validators: typing.Sequence[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )
    subclasses_relation: typing.Optional[str] = None
    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False
