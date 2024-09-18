import functools
import inspect
import types
import typing

import pydantic

from pangloss.model_config.models_base import (
    ReferenceViewBase,
    EdgeModel,
    ReferenceSetBase,
)
from pangloss.models import BaseNode, HeritableTrait, NonHeritableTrait, ReifiedRelation

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import RootNode
    from pangloss.model_config.field_definitions import RelationFieldDefinition


def generic_get_subclasses[T](cls: type[T] | None) -> set[type[T]] | set:
    if not cls:
        return set()
    subclasses = []
    for subclass in cls.__subclasses__():
        subclasses.append(subclass)
        subclasses.extend(generic_get_subclasses(subclass))

    return set(subclasses)


def get_all_subclasses(cls, include_abstract: bool = False) -> set[type["BaseNode"]]:
    """Get all subclasses of a BaseNode type"""

    subclasses = []
    for subclass in cls.__subclasses__():
        if not subclass.__abstract__ or include_abstract:
            subclasses += [subclass, *get_all_subclasses(subclass)]
        else:
            subclasses += get_all_subclasses(subclass)
    return set(subclasses)


def get_trait_subclasses(
    trait: type[HeritableTrait] | type[NonHeritableTrait],
) -> set[type[HeritableTrait] | type[NonHeritableTrait]]:
    """Get subclasses of a Trait that are Traits, not instantiations
    of a Trait"""

    subclasses = [trait]
    for subclass in trait.__subclasses__():
        if model_is_trait(subclass):
            subclasses.extend(get_trait_subclasses(subclass))
    return set(subclasses)


def is_subclass_of_heritable_trait(
    cls: type[HeritableTrait] | type[NonHeritableTrait],
) -> bool:
    """Determine whether a class is a subclass of a Trait,
    not the application of a trait to a real BaseNode class.

    This should work by not having BaseNode in its class hierarchy
    """
    for parent in cls.mro()[1:]:
        if issubclass(parent, BaseNode):
            return False
    else:
        return True


def model_is_trait(
    cls: type[BaseNode] | type[HeritableTrait] | type[NonHeritableTrait],
):
    """Determines whether a model is a Trait, or subclass of a Trait,
    rather than a BaseNode type to which a Trait has been applied"""

    return (
        inspect.isclass(cls)
        and issubclass(cls, (HeritableTrait, NonHeritableTrait))
        and is_subclass_of_heritable_trait(cls)
    )


def get_direct_instantiations_of_trait(
    trait: type[HeritableTrait] | type[NonHeritableTrait],
    follow_trait_subclasses: bool = False,
):
    """Given a Trait class, find the models to which it is *directly* applied,
    i.e. omitting children"""

    if follow_trait_subclasses:
        trait_subclasses = [
            trait_subclass for trait_subclass in get_trait_subclasses(trait)
        ]
        instantiations_of_trait = []
        for trait_subclass in trait_subclasses:
            instantiations_of_trait.extend(
                subclass
                for subclass in trait_subclass.__subclasses__()
                if issubclass(subclass, BaseNode)
            )
        return set(instantiations_of_trait)

    return set(
        [
            subclass
            for subclass in trait.__subclasses__()
            if issubclass(subclass, BaseNode)
        ]
    )


def get_subclasses_of_reified_relations(cls: type[ReifiedRelation]):
    """Gets the subclasses of a ReifiedRelation, with following rules:

    Where a generic type is passed with a type argument, the subclasses are found
    and applied with the same argument.

    Where a ReifiedRelation has a type already manually bound, the subclasses of
    this class are found.
    """

    # If it is a generic type...
    if origin_type := cls.__pydantic_generic_metadata__.get("origin", False):
        subclasses = set()
        # ... get all the subclasses of the generic type...
        for subclass in generic_get_subclasses(origin_type):
            origin = subclass.__pydantic_generic_metadata__.get("origin", False)
            args = subclass.__pydantic_generic_metadata__.get("args", False)
            # ... and, checking the wrapped type is something real...
            if (
                args
                and inspect.isclass(args[0])
                and issubclass(
                    args[0],
                    (BaseNode, ReifiedRelation, HeritableTrait, NonHeritableTrait),
                )
            ):
                # ...get the subclasses of that type which are generic (i.e. have "parameters")
                subclasses.add(subclass)
                # ... get all the subclasses of that, and construct types out of that
                # by applying the original arg
                for ssc in generic_get_subclasses(origin):
                    if ssc.__pydantic_generic_metadata__.get("parameters"):
                        subclasses.add(ssc[*args])  # type: ignore
        return subclasses
    else:
        # Otherwise, it's a non-generic type; just get the subclasses and itself
        return set([cls, *generic_get_subclasses(cls)])


def get_concrete_model_types(
    classes: type["RootNode"]
    | type[HeritableTrait]
    | type[NonHeritableTrait]
    | types.UnionType
    | type[ReifiedRelation],
    include_subclasses: bool = False,
    include_abstract: bool = False,
    follow_trait_subclasses: bool = False,
) -> set[type[BaseNode]]:
    concrete_model_types = []

    if typing.get_origin(classes) is types.UnionType:
        for cl in typing.get_args(classes):
            concrete_model_types.extend(
                get_concrete_model_types(
                    cl,
                    include_abstract=include_abstract,
                    include_subclasses=include_subclasses,
                )
            )
    elif (
        inspect.isclass(classes)
        and issubclass(classes, HeritableTrait)
        and model_is_trait(classes)
    ):
        for instantiated_trait in get_direct_instantiations_of_trait(
            classes, follow_trait_subclasses=follow_trait_subclasses
        ):
            if not instantiated_trait.__abstract__ or include_abstract:
                concrete_model_types.append(instantiated_trait)
            if include_subclasses:
                concrete_model_types.extend(
                    get_all_subclasses(
                        instantiated_trait, include_abstract=include_abstract
                    )
                )
    elif (
        inspect.isclass(classes)
        and issubclass(classes, NonHeritableTrait)
        and model_is_trait(classes)
    ):
        for instantiated_trait in get_direct_instantiations_of_trait(
            classes, follow_trait_subclasses=follow_trait_subclasses
        ):
            if not instantiated_trait.__abstract__ or include_abstract:
                concrete_model_types.append(instantiated_trait)
    elif inspect.isclass(classes) and issubclass(classes, ReifiedRelation):
        concrete_model_types.extend(get_subclasses_of_reified_relations(classes))

    elif inspect.isclass(classes) and issubclass(classes, BaseNode):
        if not classes.__abstract__ or include_abstract:
            concrete_model_types.append(classes)

        if include_subclasses:
            concrete_model_types.extend(
                get_all_subclasses(classes, include_abstract=include_abstract)
            )

    return typing.cast(set[type[BaseNode]], set(concrete_model_types))


def get_non_heritable_traits_as_direct_ancestors(
    cls: type[BaseNode],
) -> set[NonHeritableTrait]:
    """Identifies NonHeritableTraits that are directly applied to a model class"""

    traits_as_direct_bases = []
    for base in cls.__bases__:
        for parent in inspect.getmro(base):
            if parent is BaseNode:
                break
            elif parent is NonHeritableTrait:
                traits_as_direct_bases.append(base)
            else:
                continue
    return set(traits_as_direct_bases)


def get_non_heritable_traits_as_indirect_ancestors(
    cls,
) -> set[NonHeritableTrait]:
    """Identifies NonHeritableTraits in a model class's hierarchy that are not
    directly applied to the class"""

    traits_as_indirect_ancestors = []
    traits_as_direct_ancestors = get_non_heritable_traits_as_direct_ancestors(cls)
    for c in cls.mro():
        if (
            issubclass(c, NonHeritableTrait)
            and not issubclass(c, BaseNode)
            and c is not NonHeritableTrait
            and c is not cls
            and c not in traits_as_direct_ancestors
        ):
            traits_as_indirect_ancestors.append(c)
    return set(traits_as_indirect_ancestors)


def create_reference_set_model_with_property_model(
    origin_model: type["RootNode"] | type["ReifiedRelation"],
    target_model: type["RootNode"] | type["ReifiedRelation"],
    edge_model: type[EdgeModel],
    field_name: str,
) -> type[ReferenceSetBase]:
    return pydantic.create_model(
        f"{origin_model.__name__}__{field_name}__{target_model.__name__}__ReferenceSet",
        __base__=ReferenceSetBase,
        type=(typing.Literal[target_model.__name__], target_model.__name__),  # type: ignore
        edge_properties=(edge_model, ...),
    )


@functools.cache
def create_reference_view_model_with_property_model(
    origin_model: type["RootNode"] | type["ReifiedRelation"],
    target_model: type["RootNode"] | type["ReifiedRelation"],
    edge_model: type[EdgeModel],
    field_name: str,
) -> type[ReferenceViewBase]:
    return pydantic.create_model(
        f"{origin_model.__name__}__{field_name}__{target_model.__name__}__ReferenceView",
        __base__=ReferenceViewBase,
        type=(typing.Literal[target_model.__name__], target_model.__name__),  # type: ignore
        edge_properties=(edge_model, ...),
    )


def recurse_embedded_models_for_all_outgoing_relation_field_definitions(
    source_class: type["RootNode"],
) -> list["RelationFieldDefinition"]:
    """Given a model, go through all embedded models to find the target of
    outgoing relations, and the relation name"""

    relation_definitions: list["RelationFieldDefinition"] = []
    for relation_definition in source_class.field_definitions.relation_fields:
        relation_definitions.append(relation_definition)
    for embedded_definition in source_class.field_definitions.embedded_fields:
        for embedded_concrete_type in embedded_definition.field_concrete_types:
            relation_definitions.extend(
                recurse_embedded_models_for_all_outgoing_relation_field_definitions(
                    embedded_concrete_type
                )
            )
    return relation_definitions


def get_paths_to_target_node(
    cls: type[ReifiedRelation], relation_definition: "RelationFieldDefinition"
):
    trees = recurse_reified_relation_definitions_into_tree(
        cls, ReifiedRelationTree((cls, relation_definition))
    )

    paths = get_paths(trees)

    return [PathToTargetRootNode(path) for path in paths]


class PathToTargetRootNode:
    def __init__(self, path: list):
        self.target: tuple[type[RootNode], "RelationFieldDefinition"] = path[-1]
        self.path_items: list[
            tuple[type[ReifiedRelation], "RelationFieldDefinition"]
        ] = path[:-1]

        path_field_names = [
            path_item.field_name for _, path_item in self.path_items[1:]
        ]
        path_field_names.append(self.target[1].field_name)
        self.path_is_all_target = all(r == "target" for r in path_field_names)
        self.selected_reverse_name: None | str = None


def get_paths(t: "ReifiedRelationTree", paths=None, current_path=None):
    if paths is None:
        paths = []
    if current_path is None:
        current_path = []

    current_path.append(t.value)
    if len(t.children) == 0:
        paths.append(current_path)
    else:
        for child in t.children:
            get_paths(child, paths, list(current_path))
    return paths


class ReifiedRelationTree:
    def __init__(
        self,
        value: tuple[
            type["RootNode"] | type["ReifiedRelation"], "RelationFieldDefinition"
        ],
    ):
        self.value = value
        self.children: list[ReifiedRelationTree] = []


def recurse_reified_relation_definitions_into_tree(cls: type[ReifiedRelation], ttree):
    from pangloss.model_config.models_base import (
        RootNode,
        ReifiedRelation,
    )

    for outgoing_relation_definition in cls.field_definitions.relation_fields:
        for concrete_related_type in outgoing_relation_definition.field_concrete_types:
            if issubclass(concrete_related_type, RootNode):
                ttree.children.append(
                    ReifiedRelationTree(
                        (concrete_related_type, outgoing_relation_definition)
                    )
                )
            if issubclass(concrete_related_type, ReifiedRelation):
                tree = ReifiedRelationTree(
                    (concrete_related_type, outgoing_relation_definition)
                )
                recurse_reified_relation_definitions_into_tree(
                    concrete_related_type, tree
                )
                ttree.children.append(tree)
    return ttree
