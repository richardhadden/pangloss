from __future__ import annotations

import collections
import dataclasses
import datetime
import inspect
import typing
import uuid

import annotated_types
import humps
import neo4j
import pydantic

from pangloss.exceptions import PanglossConfigError

if typing.TYPE_CHECKING:
    from pangloss.model_config.field_definitions import (
        IncomingRelationDefinition,
        ModelFieldDefinitions,
    )
    from pangloss.models import BaseNode

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

    @property
    def labels(self) -> set[str]:
        return typing.cast(set[str], self.base_class.labels)


STANDARD_MODEL_CONFIG: pydantic.ConfigDict = {
    "alias_generator": humps.camelize,
    "populate_by_name": True,
    "use_enum_values": True,
}


class _GenericNode(pydantic.BaseModel):
    """Standard fields for node types"""

    type: str
    # label: str

    model_config = {
        "alias_generator": humps.camelize,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

    def __init__(self, *args, **kwargs):
        """
        When initialising, any dot-separated property of a neo4j representation of
        a relation property, ie. relation_name.relation_field_name; these need to be
        splint and added as "relation_properties" before initialising the instance
        """
        if "edge_properties" not in kwargs:
            kwargs["edge_properties"] = {}

        for key, value in kwargs.items():
            if "." in key:
                kwargs["edge_properties"][key.split(".")[1]] = value
        super().__init__(*args, **kwargs)


class _ExtantNodeMixin:
    """Contains the fields that a model will have once it is created"""

    uuid: uuid.UUID

    is_deleted: bool = False

    @pydantic.field_validator("*", mode="before")
    @classmethod
    def convert_neo4j_dates(cls, value: typing.Any, field) -> typing.Any:
        if isinstance(value, (neo4j.time.DateTime, neo4j.time.Date)):
            return value.to_native()
        return value


class MultiKeyField[T](pydantic.BaseModel):
    value: T

    field_definitions_initialised: typing.ClassVar[bool]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]

    @classmethod
    def __pydantic_init_subclass__(cls):
        # Needs to be set on a per-class basis on subclassing, not
        # inherited for each class
        cls.field_definitions_initialised = False


class ReifiedRelation[T](pydantic.BaseModel):
    """Defines a model for a Reified Relation (a relation through a node)

    `target` parameter must be present, either defined using generic class
    or explicitly overridden by subclass

    """

    target: typing.Annotated[T, RelationConfig(reverse_name="is_target_of")]
    type: str

    View: typing.ClassVar[type[ReifiedRelationViewBase]]
    EditSet: typing.ClassVar[type[EditSetBase]]

    field_definitions_initialised: typing.ClassVar[bool]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]
    labels: typing.ClassVar[set[str]]

    model_config = STANDARD_MODEL_CONFIG

    @classmethod
    def __pydantic_init_subclass__(cls):
        # Needs to be set on a per-class basis on subclassing, not
        # inherited for each class
        cls.field_definitions_initialised = False

        cls.labels = set()

        for parent_class in cls.mro():
            if (
                issubclass(parent_class, ReifiedRelation)
                and "[" not in parent_class.__name__
            ):
                cls.labels.add(parent_class.__name__)


class ReifiedRelationNode[T](ReifiedRelation[T]):
    """Subclass of Reified Relation with full BaseNode-type behaviour, i.e.
    can be viewable separately, having own label etc."""

    label: str
    View: typing.ClassVar[type[ViewBase]]


class ReifiedRelationViewBase(pydantic.BaseModel, _SubNodeProxy):
    """Base model for getting ReifiedRelation"""

    type: str
    uuid: uuid.UUID
    head_uuid: typing.Optional[uuid.UUID] = None
    head_type: typing.Optional[str] = None
    generated: typing.ClassVar[bool] = True
    model_config = STANDARD_MODEL_CONFIG


def collect_multi_key_field_to_dict(kwargs: dict) -> dict:
    # Transform MultiKeyField from `field_name____subfield_name = value`
    # into `field_name: {subfield_name: value}` by splitting on
    grouped_multi_key_fields = collections.defaultdict(dict)
    for key, value in kwargs.items():
        if "____" in key:
            field_name, subfield_name = key.split("____")
            grouped_multi_key_fields[field_name][subfield_name] = value

    kwargs = {**kwargs, **grouped_multi_key_fields}
    return kwargs


class EditViewBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for getting model to edit"""

    def __init__(self, *args, **kwargs):
        kwargs = collect_multi_key_field_to_dict(kwargs)
        super().__init__(*args, **kwargs)

    async def update(self) -> bool:
        return await typing.cast(type["BaseNode"], self.base_class)._update_method(self)


class EditSetBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for inputting edited model"""

    async def update(self, username: str | None = None) -> bool:
        return await typing.cast(type["BaseNode"], self.base_class)._update_method(
            self, username=username
        )


class ViewBase(_GenericNode, _ExtantNodeMixin, _SubNodeProxy):
    """Base model for viewing model"""

    label: str
    # _head_uuid: uuid.UUID
    generated: typing.ClassVar[bool] = True
    head_uuid: typing.Optional[uuid.UUID] = None
    head_type: typing.Optional[str] = None

    # TODO: Remove the created Optional and adjust tests accordingly

    def __init__(self, *args, **kwargs):
        kwargs = collect_multi_key_field_to_dict(kwargs)
        super().__init__(*args, **kwargs)


class HeadViewBase(ViewBase):
    label: str
    created_by: typing.Optional[str]
    created_when: typing.Optional[datetime.datetime]
    modified_by: typing.Optional[str]
    modified_when: typing.Optional[datetime.datetime]


# Reference types need to be separated, so that additional fields for viewing
# can be added for list-views, etc., while still only requiring necessary fields
# (type and uuid) for setting relations


class ReferenceViewBase(_GenericNode, _SubNodeProxy):
    """Base model for viewing reference to a model

    Requires uuid, type and label
    """

    uuid: uuid.UUID
    label: str
    model_config = STANDARD_MODEL_CONFIG
    head_uuid: typing.Optional[uuid.UUID] = None
    head_type: typing.Optional[str] = None

    def __hash__(self):
        return hash(self.uuid)


class ReferenceSetBase(pydantic.BaseModel, _SubNodeProxy):
    """Base model for setting reference to a model

    Requires only the type of the model and the uuid
    """

    type: str
    uuid: uuid.UUID
    field_definitions_initialised: typing.ClassVar[bool]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]

    model_config = STANDARD_MODEL_CONFIG

    def _as_dict(self):
        return {"type": self.type, "uuid": self.uuid}

    @classmethod
    def __pydantic_init_subclass__(cls):
        from pangloss.model_config.model_setup_functions import (
            initialise_model_field_definitions,
        )

        # TODO: WRITE TEST THAT THIS ACTUALLY WORKS!
        cls.field_definitions_initialised = False

        initialise_model_field_definitions(cls)


class EmbeddedCreateBase(pydantic.BaseModel, _SubNodeProxy):
    """Model for creating an embedded node"""

    type: str
    model_config = {
        "alias_generator": humps.camelize,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class EmbeddedSetBase(pydantic.BaseModel, _SubNodeProxy):
    """Model for setting an embedded node"""

    uuid: uuid.UUID
    type: str
    model_config = {
        "alias_generator": humps.camelize,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }


class EmbeddedViewBase(pydantic.BaseModel, _SubNodeProxy):
    type: str
    uuid: uuid.UUID
    model_config = {
        "alias_generator": humps.camelize,
        "populate_by_name": True,
        "arbitrary_types_allowed": True,
    }

    @pydantic.field_validator("*", mode="before")
    @classmethod
    def convert_neo4j_dates(cls, value: typing.Any, field) -> typing.Any:
        if isinstance(value, (neo4j.time.Date, neo4j.time.DateTime)):
            return value.to_native()
        return value


@dataclasses.dataclass
class BaseMeta:
    """Base class for BaseNode Meta fields"""

    abstract: bool = False
    create: bool = True
    edit: bool = True
    delete: bool = True


class RootNode(_GenericNode):
    """Default base model on creation"""

    label: str

    HeadView: typing.ClassVar[type[HeadViewBase]]
    View: typing.ClassVar[type[ViewBase]]
    EditView: typing.ClassVar[type[EditViewBase]]
    EditSet: typing.ClassVar[type[EditSetBase]]
    ReferenceView: typing.ClassVar[type[ReferenceViewBase]]
    ReferenceSet: typing.ClassVar[type[ReferenceSetBase]]
    Embedded: typing.ClassVar[type[EmbeddedCreateBase]]
    EmbeddedSet: typing.ClassVar[type[EmbeddedSetBase]]
    EmbeddedView: typing.ClassVar[type[EmbeddedViewBase]]

    field_definitions_initialised: typing.ClassVar[bool]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]
    incoming_relation_definitions: typing.ClassVar[
        dict[str, set["IncomingRelationDefinition"]]
    ]
    subclassed_fields_to_delete: typing.ClassVar[list[str]]
    labels: typing.ClassVar[set[str]]
    Meta: typing.ClassVar[type[BaseMeta]] = BaseMeta

    def __init_subclass__(cls):
        # Needs to be set on a per-class basis on subclassing, not
        # inherited for each class
        cls.field_definitions_initialised = False
        cls.subclassed_fields_to_delete = []

        initialise_model_meta_inheritance(cls)


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


class EdgeModel(pydantic.BaseModel):
    show_in_reverse_relation: typing.ClassVar[bool] = False
    model_config = STANDARD_MODEL_CONFIG

    field_definitions_initialised: typing.ClassVar[bool]
    field_definitions: typing.ClassVar["ModelFieldDefinitions"]

    @classmethod
    def __pydantic_init_subclass__(cls) -> None:
        from pangloss.model_config.model_setup_functions import (
            initialise_model_field_definitions,
        )

        # TODO: WRITE TEST THAT THIS ACTUALLY WORKS!
        cls.field_definitions_initialised = False

        initialise_model_field_definitions(cls)


@dataclasses.dataclass
class RelationConfig:
    reverse_name: str
    subclasses_relation: typing.Optional[list[str] | frozenset[str]] = None
    edge_model: typing.Optional[type["EdgeModel"]] = None
    validators: typing.Sequence[annotated_types.BaseMetadata] = dataclasses.field(
        default_factory=list
    )

    create_inline: bool = False
    edit_inline: bool = False
    delete_related_on_detach: bool = False

    def __hash__(self):
        if self.subclasses_relation:
            self.subclasses_relation = frozenset(self.subclasses_relation)
        return hash(self.__dict__)


def initialise_model_meta_inheritance(cls: type[RootNode]):
    # Check cls.Meta is a subclass of BaseMeta
    if hasattr(cls, "Meta") and not issubclass(cls.Meta, BaseMeta):
        raise PanglossConfigError(
            f"Model <{cls.__name__}> has a Meta object not inherited from BaseMeta"
        )

    # Check BaseMeta is not used with some name other than cls.Meta
    for class_var_name in cls.__class_vars__:
        if (
            getattr(cls, class_var_name, None)
            and inspect.isclass(getattr(cls, class_var_name))
            and issubclass(getattr(cls, class_var_name), BaseMeta)
            and class_var_name != "Meta"
        ):
            raise PanglossConfigError(
                f"Error with model <{cls.__name__}>: BaseMeta must be inherited from by a class called Meta"
            )

    # Check BaseMeta is not used with some name other than cls.Meta, this time in the class dict
    for field_name in cls.__dict__:
        if (
            getattr(cls, field_name, None)
            and inspect.isclass(getattr(cls, field_name))
            and issubclass(getattr(cls, field_name), BaseMeta)
            and field_name != "Meta"
        ):
            raise PanglossConfigError(
                f"Error with model <{cls.__name__}>: BaseMeta must be inherited from by a class called Meta"
            )

    parent_class = [c for c in cls.mro() if issubclass(c, RootNode) and c is not cls][0]
    parent_meta = parent_class.Meta

    if "Meta" not in cls.__dict__:
        meta_settings = {}
        for field_name in BaseMeta.__dataclass_fields__:
            meta_settings[field_name] = getattr(parent_meta, field_name)
        meta_settings["abstract"] = False

        cls.Meta = type("Meta", (BaseMeta,), meta_settings)

    else:
        meta_settings = {}
        for field_name in BaseMeta.__dataclass_fields__:
            if field_name == "abstract":
                continue

            if field_name in cls.Meta.__dict__:
                meta_settings[field_name] = cls.Meta.__dict__[field_name]
            else:
                meta_settings[field_name] = parent_meta.__dict__[field_name]
        if "abstract" in cls.Meta.__dict__ and cls.Meta.__dict__["abstract"] is True:
            meta_settings["abstract"] = True

        cls.Meta = type("Meta", (BaseMeta,), meta_settings)
