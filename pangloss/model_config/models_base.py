from __future__ import annotations

import dataclasses
import datetime
import typing
import uuid

import annotated_types
import humps
import pydantic

if typing.TYPE_CHECKING:
    from field_definitions import ModelFieldDefinitions, IncomingRelationDefinition

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
    """Internal mixin class to proxy methods/fields from Node additional types (View, EditView)
    to the BaseNode type"""

    base_class: typing.ClassVar[type["RootNode"] | type["ReifiedRelation"]]

    @property
    def field_definitions(self) -> "ModelFieldDefinitions":
        return self.base_class.field_definitions


STANDARD_MODEL_CONFIG: pydantic.ConfigDict = {
    "alias_generator": humps.camelize,
    "populate_by_name": True,
    "use_enum_values": True,
}


class _GenericNode(pydantic.BaseModel):
    """Standard fields for node types"""

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


class ReifiedRelation[T](pydantic.BaseModel, _SubNodeProxy):
    """Defines a model for a Reified Relation (a relation through a node)

    `target` parameter must be present, either defined using generic class
    or explicitly overridden by subclass

    """

    target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
    type: str

    View: typing.ClassVar[type[ViewBase]]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]

    model_config = STANDARD_MODEL_CONFIG


class ReifiedRelationNode[T](ReifiedRelation[T]):
    """Subclass of Reified Relation with full BaseNode-type behaviour, i.e.
    can be viewable separately, having own label etc."""

    label: str


class EditViewBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for getting model to edit"""

    pass


class EditSetBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for inputting edited model"""

    pass


class ViewBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for viewing model"""

    generated: typing.ClassVar[bool] = True


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
    """Model for setting an embedded node"""

    type: str


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
    incoming_relation_definitions: typing.ClassVar[
        dict[str, "IncomingRelationDefinition"]
    ]

    __abstract__: typing.ClassVar[bool] = True


class HeritableTrait:
    pass


class NonHeritableTrait:
    pass


class Embedded[T]:
    """Embed a BaseNode type within another node, so that it is functionally
    part of the container node.
    """

    pass


class IncomingRelationView(pydantic.BaseModel):
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
