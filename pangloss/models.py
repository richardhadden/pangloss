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
from pangloss.neo4j.database_mixins import DatabaseQueryMixin

reexported = (
    ReifiedRelation,
    RelationConfig,
    Embedded,
    MultiKeyField,
    BaseMeta,
    ReferenceSetBase,
    ReifiedRelationNode,
)


class BaseNode(RootNode, DatabaseQueryMixin):
    type: str
    label: str
