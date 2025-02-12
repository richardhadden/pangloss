from pangloss_new.model_config.models_base import (
    Embedded,
    MultiKeyField,
    ReifiedRelation,
    RelationConfig,
    RootNode,
)

reexported = (
    ReifiedRelation,
    RelationConfig,
    Embedded,
    MultiKeyField,
)


class BaseNode(RootNode):
    type: str
    label: str
