import typing

import humps
from pydantic import ConfigDict, model_validator

if typing.TYPE_CHECKING:
    from models_base import (
        CreateBase,
        EditHeadSetBase,
        EditSetBase,
        ModelFieldDefinitions,
        ReferenceSetBase,
        ReifiedCreateBase,
        ReifiedRelation,
        ReifiedRelationViewBase,
        RootNode,
        ViewBase,
    )

STANDARD_MODEL_CONFIG: ConfigDict = {
    "alias_generator": humps.camelize,
    "populate_by_name": True,
    "use_enum_values": True,
    "arbitrary_types_allowed": True,
}


class _StandardModel:
    model_config = STANDARD_MODEL_CONFIG


class _BindingSubModelValidator[T]:
    _has_bindable_relations: typing.ClassVar[bool] = False
    _bindable_relations: typing.ClassVar[list]

    @classmethod
    def set_has_bindable_relations(cls) -> None:
        bindable_relations = [
            rf
            for rf in typing.cast(
                type["CreateBase | EditHeadSetBase | EditSetBase"], cls
            ).__pg_base_class__._meta.fields.relation_fields
            if rf.bind_fields_to_related
        ]
        if bindable_relations:
            cls._bindable_relations = bindable_relations
            cls._has_bindable_relations = True

    @model_validator(mode="before")
    @classmethod
    def binding_submodel_validator(cls, data):
        if not cls._has_bindable_relations:
            return data

        for bindable_relation in cls._bindable_relations:
            assert bindable_relation.bind_fields_to_related

            for binding_def in bindable_relation.bind_fields_to_related:
                if data[binding_def[0]]:
                    for c in data[bindable_relation.field_name]:
                        if not c.get(binding_def[1], None):
                            if len(binding_def) == 3:
                                c[binding_def[1]] = binding_def[2](data[binding_def[0]])
                            else:
                                c[binding_def[1]] = data[binding_def[0]]

        return data


class _OwnsMethods:
    """Adds methods to check whether a model has attribute
    set on itself, not in inheritance chain, by inspecting cls.__dict__"""

    @classmethod
    def has_own(cls, key: str) -> bool:
        if key in cls.__dict__:
            return True
        if item := getattr(cls, key, None) and hasattr(cls, "__pg_base_class__"):
            if getattr(item, "__pg_base_class__", None) is cls:
                return True
        return False

    @classmethod
    def get_own(cls, key: str) -> typing.Any:
        return cls.__dict__.get(key, None)


class _BaseClassProxy(_OwnsMethods):
    __pg_annotations__: typing.ClassVar[dict[str, typing.Any]]
    __pg_base_class__: typing.ClassVar[type["RootNode"] | type["ReifiedRelation"]]
    __pg_specialist_type_fields_definitions__: typing.ClassVar["ModelFieldDefinitions"]

    @property
    def __pg_field_definitions__(self):
        return (self.__pg_base_class__.__pg_field_definitions__,)

    @property
    def collapse_when(self):
        return getattr(self.__pg_base_class__, "collapse_when", None)


RelationViaEdgeType = typing.TypeVar(
    "RelationViaEdgeType", bound="type[ReferenceSetBase | ReifiedCreateBase]"
)


class RelationsViaEdge(typing.Generic[RelationViaEdgeType]):
    _classes: dict[str, type[RelationViaEdgeType]]

    def __init__(self):
        self._classes = {}

    def _add(self, edge_model_name: str, model: type[RelationViaEdgeType]):
        if edge_model_name not in self._classes:
            self._classes[edge_model_name] = model

    def __getattr__(self, name: str) -> type[RelationViaEdgeType] | None:
        try:
            return getattr(super(), name)
        except AttributeError:
            if name in self._classes:
                return self._classes[name]
            else:
                raise AttributeError


class _ViaEdge(typing.Generic[RelationViaEdgeType]):
    via: typing.ClassVar[RelationsViaEdge[RelationViaEdgeType]]  # type: ignore

    def __init_subclass__(cls) -> None:
        cls.via = RelationsViaEdge[RelationViaEdgeType]()
        return super().__init_subclass__()


ViewInContextType = typing.TypeVar(
    "ViewInContextType", bound="type[ViewBase | ReifiedRelationViewBase]"
)


class ContextFieldName[V]:
    _context_field_names: dict[str, V]

    def __init__(self):
        self._context_field_names = {}

    def _add(
        self,
        reverse_field_name: str,
        view_in_context_model: V,
    ):
        self._context_field_names[reverse_field_name] = view_in_context_model

    def __getattr__(self, name: str) -> V | None:
        try:
            return getattr(super(), name)
        except AttributeError:
            if name in self._context_field_names:
                return self._context_field_names[name]
            else:
                raise AttributeError


# Event.View.in_context_of.Cat.is_involved_in = ContextViewModel
#           ^target


class ViewInContext(typing.Generic[ViewInContextType]):
    _classes: dict[str, ContextFieldName[type[ViewInContextType]]]
    _cls: type[ViewInContextType]

    def __init__(self, cls):
        self._cls = cls
        self._classes = dict()

    def _add(
        self,
        relation_target_model: type["RootNode"],
        view_in_context_model: type[ViewInContextType],
        reverse_field_name: str,
    ):
        if relation_target_model.__name__ not in self._classes:
            self._classes[relation_target_model.__name__] = ContextFieldName()
        self._classes[relation_target_model.__name__]._add(
            reverse_field_name=reverse_field_name,
            view_in_context_model=view_in_context_model,
        )

    def __getattr__(
        self, name: str
    ) -> ContextFieldName[type[ViewInContextType]] | None:
        try:
            return getattr(super(), name)
        except AttributeError:
            if name in self._classes:
                return self._classes[name]
            else:
                raise AttributeError(
                    f"{self._cls.__pg_base_class__.__name__}"
                    f".{self._cls.__name__.replace(self._cls.__pg_base_class__.__name__, '')} "
                    f"has no reverse context model for {name}"
                )


class _ReverseRelationInContextOf(typing.Generic[ViewInContextType]):
    in_context_of: typing.ClassVar[ViewInContext[ViewInContextType]]  # type: ignore

    def __init_subclass__(cls) -> None:
        cls.in_context_of = ViewInContext[ViewInContextType](cls)
        return super().__init_subclass__()
