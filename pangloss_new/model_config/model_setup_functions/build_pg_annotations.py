import typing
from collections import ChainMap

if typing.TYPE_CHECKING:
    from pangloss_new.model_config.models_base import RootNode


def build_pg_annotations(cls: type["RootNode"]) -> None:
    """Set the __pg_annotations__ of the class to a ChainMap
    gathering the class's own annotations and all parent class annotations
    up to (but not including) BaseNode.

    Better to do this once on initialisation of models than to do it
    dynamically and try to fake a @classmethod+@property.
    """

    from pangloss_new.model_config.models_base import ReifiedBase
    from pangloss_new.models import BaseNode

    annotation_dicts = []
    for parent in cls.mro():
        print(parent)
        if parent is BaseNode or parent is ReifiedBase:
            break
        annotation_dicts.append(parent.__annotations__)
    cls.__pg_annotations__ = ChainMap(*annotation_dicts)
