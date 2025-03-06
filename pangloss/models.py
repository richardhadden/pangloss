from pangloss.model_config.models_base import (
    BaseMeta,
    Embedded,
    MultiKeyField,
    ReferenceSetBase,
    ReifiedRelation,
    ReifiedRelationNode,
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
    ReifiedRelationNode,
)


class BaseNode(RootNode):
    type: str
    label: str
