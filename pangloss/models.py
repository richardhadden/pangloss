from pangloss.model_config.models_base import (
    BaseMeta,
    Embedded,
    MultiKeyField,
    ReferenceSetBase,
    ReifiedRelation,
    RelationConfig,
    RootNode,
)

reexported = (
    ReifiedRelation,
    RelationConfig,
    Embedded,
    MultiKeyField,
    BaseMeta,
    ReferenceSetBase,
)


class BaseNode(RootNode):
    type: str
    label: str
