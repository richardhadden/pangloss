import datetime
import typing
import uuid

from uuid_extensions import uuid7

from pangloss.model_config.models_base import RootNode, ReifiedRelation
from pangloss.cypher.utils import (
    Identifier,
    CreateQuery,
    QuerySubstring,
    get_properties_as_writeable_dict,
    join_labels,
)


def build_create_node_query_object(
    instance: RootNode | ReifiedRelation,
    query: CreateQuery | None = None,
    extra_labels: list[str] | None = None,
    start_node: bool = False,
    user: str = "DefaultUser",
) -> CreateQuery:
    if not query:
        query = CreateQuery()

    if not extra_labels:
        extra_labels = []

    node_identifier = Identifier()
    node_data_identifier = Identifier()

    query.uuid = typing.cast(uuid.UUID, uuid7())

    query.query_params[node_data_identifier] = get_properties_as_writeable_dict(
        instance,
        extras={
            "created_by": user,
            "created_when": datetime.datetime.now(),
            "modified_by": user,
            "modified_when": datetime.datetime.now(),
            "uuid": query.uuid,
        },
    )

    node_labels_string = join_labels(instance.labels, extra_labels)

    query.create_query_strings.append(
        QuerySubstring(f"""CREATE ({node_identifier}:{node_labels_string} {{uuid: "{str(query.uuid)}"}})
SET {node_identifier} = ${node_data_identifier}""")
    )

    if start_node:
        query.return_identifier = node_identifier

    return query
