import inspect
import types
import typing

from pangloss.models import BaseNode, HeritableTrait, NonHeritableTrait


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


def get_concrete_model_types(
    classes: type[BaseNode]
    | type[HeritableTrait]
    | type[NonHeritableTrait]
    | types.UnionType,
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

    elif inspect.isclass(classes) and issubclass(classes, BaseNode):
        if not classes.__abstract__ or include_abstract:
            concrete_model_types.append(classes)

        if include_subclasses:
            concrete_model_types.extend(
                get_all_subclasses(classes, include_abstract=include_abstract)
            )

    return set(concrete_model_types)
