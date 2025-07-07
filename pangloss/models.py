from pangloss.model_config.models_base import (
    BaseMeta,
    EdgeModel,
    Embedded,
    HeritableTrait,
    MultiKeyField,
    NonHeritableTrait,
    ReferenceSetBase,
    ReifiedMeta,
    ReifiedRelation,
    ReifiedRelationNode,
    RelationConfig,
    RootNode,
    SemanticSpace,
    SemanticSpaceMeta,
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
    EdgeModel,
    HeritableTrait,
    NonHeritableTrait,
    SemanticSpace,
    SemanticSpaceMeta,
    ReifiedMeta,
)


class BaseNode(RootNode, DatabaseQueryMixin):
    type: str
    label: str
