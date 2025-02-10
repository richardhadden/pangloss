from pangloss_new.model_config.models_base import (
    ReifiedRelation,
    RelationConfig,
    RootNode,
)

reexported = (
    ReifiedRelation,
    RelationConfig,
)


class BaseNode(RootNode):
    type: str
    label: str
