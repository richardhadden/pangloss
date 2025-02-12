from pangloss_new.model_config.models_base import (
    Embedded,
    ReifiedRelation,
    RelationConfig,
    RootNode,
)

reexported = (
    ReifiedRelation,
    RelationConfig,
    Embedded,
)


class BaseNode(RootNode):
    type: str
    label: str
