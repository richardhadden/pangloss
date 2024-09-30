import datetime
import typing
import uuid

from uuid_extensions import uuid7


from pangloss.cypher.utils import (
    Identifier,
    CreateQuery,
    QuerySubstring,
    get_properties_as_writeable_dict,
    convert_dict_for_writing,
    join_labels,
)

if typing.TYPE_CHECKING:
    from pangloss.model_config.field_definitions import RelationFieldDefinition
    from pangloss.model_config.models_base import (
        RootNode,
        ReifiedRelation,
        ReferenceSetBase,
    )


def build_create_relationship_to_existing(
    relation_to_target: "ReferenceSetBase",
    relation_definition: "RelationFieldDefinition",
    source_node_identifier: str,
    query: CreateQuery,
):
    matched_node_identifier = Identifier()
    relation_identifier = Identifier()

    edge_properties = {
        "relation_labels": relation_definition.relation_labels,
        "reverse_relation_labels": relation_definition.reverse_relation_labels,
    }
    if hasattr(relation_to_target, "edge_model"):
        edge_properties["edge_properties"] = relation_to_target.edge_model  # type: ignore

    edge_properties = convert_dict_for_writing(edge_properties)

    edge_properties_identifier = Identifier()

    query.query_params[edge_properties_identifier] = edge_properties

    query.match_query_strings.append(
        f"""MATCH ({matched_node_identifier} {{uuid: "{relation_to_target.uuid}"}})"""
    )
    query.create_query_strings.append(
        f"""CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({matched_node_identifier})
        SET {relation_identifier} = ${edge_properties_identifier}"""
    )


def build_create_node_query_object(
    instance: "RootNode | ReifiedRelation",
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

    for relation_definition in instance.field_definitions.relation_fields:
        if relation_definition.create_inline:
            pass
        else:
            for related_instance in getattr(
                instance, relation_definition.field_name, []
            ):
                build_create_relationship_to_existing(
                    relation_to_target=related_instance,
                    relation_definition=relation_definition,
                    source_node_identifier=node_identifier,
                    query=query,
                )

    return query
