import typing
from collections import ChainMap

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.models_base import EdgeModel, ReifiedBase, RootNode


def build_pg_annotations(
    cls: type["RootNode"] | type["ReifiedBase"] | type["EdgeModel"],
) -> None:
    """Set the __pg_annotations__ of the class to a ChainMap
    gathering the class's own annotations and all parent class annotations
    up to (but not including) BaseNode.

    Better to do this once on initialisation of models than to do it
    dynamically and try to fake a @classmethod+@property.
    """

    from pangloss_new.model_config.models_base import EdgeModel, ReifiedBase
    from pangloss_new.models import BaseNode

    annotation_dicts = []
    for parent in cls.mro():
        if parent is BaseNode or parent is ReifiedBase or parent is EdgeModel:
            break
        annotation_dicts.append(parent.__annotations__)
    cls.__pg_annotations__ = ChainMap(*annotation_dicts)
