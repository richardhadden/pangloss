import typing

from pangloss.model_config.models_base import RootNode, ReifiedRelation
from pangloss.cypher.utils import (
    Identifier,
    QuerySubstring,
    QueryParams,
    get_properties_as_writeable_dict,
    join_labels,
)


def build_create_node_subquery(
    instance: RootNode | ReifiedRelation,
    extra_labels: list[str] | None = None,
) -> tuple[Identifier, QuerySubstring, dict[Identifier, typing.Any]]:
    if not extra_labels:
        extra_labels = []

    node_identifier = Identifier()

    node_data_identifier = Identifier()

    query_params = QueryParams(
        {node_data_identifier: get_properties_as_writeable_dict(instance)}
    )

    node_labels_string = join_labels(instance.labels, extra_labels)
    query = QuerySubstring(f"""
        CREATE (n:{node_labels_string})
        SET n = ${node_data_identifier}
    """)

    return node_identifier, query, query_params
