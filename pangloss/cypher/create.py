import typing
import uuid

import jsonpatch
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
    from pangloss.model_config.field_definitions import (
        RelationFieldDefinition,
        EmbeddedFieldDefinition,
    )
    from pangloss.model_config.models_base import (
        RootNode,
        ReifiedRelation,
        ReferenceSetBase,
        EmbeddedCreateBase,
    )
from pangloss.cypher.utils import UpdateQuery


def build_create_relationship(
    relation_to_target: "ReferenceSetBase | RootNode",
    relation_definition: "RelationFieldDefinition | EmbeddedFieldDefinition",
    source_node_identifier: str,
    query: CreateQuery | UpdateQuery,
):
    from pangloss.model_config.models_base import ReifiedRelation

    matched_node_identifier = Identifier()
    relation_identifier = Identifier()

    edge_properties = {}

    if relation_definition.field_metatype == "Relation":
        edge_properties.update(
            {
                "reverse_name": relation_definition.reverse_name,
                "relation_labels": relation_definition.relation_labels,
                "reverse_relation_labels": relation_definition.reverse_relation_labels,
            }
        )

    if hasattr(relation_to_target, "edge_properties"):
        edge_properties.update(relation_to_target.edge_properties)  # type: ignore

    edge_properties = convert_dict_for_writing(edge_properties)

    edge_properties_identifier = Identifier()

    query.query_params[edge_properties_identifier] = edge_properties

    if relation_definition.field_metatype == "Embedded":
        extra_labels = ["Embedded", "DetachDelete"]
        create_node_query, new_node_identifier, _ = build_create_node_query_object(
            typing.cast("RootNode", relation_to_target),
            query=query,
            extra_labels=extra_labels,
        )

        query.create_query_strings.append(
            f"""CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({new_node_identifier})
            SET {relation_identifier} = ${edge_properties_identifier}"""
        )

    elif relation_definition.create_inline:
        extra_labels = ["ReadInline", "CreateInline", "DetachDelete"]
        if relation_definition.edit_inline:
            extra_labels.append("EditInline")
        create_node_query, new_node_identifier, _ = build_create_node_query_object(
            typing.cast("RootNode", relation_to_target),
            query=query,
            extra_labels=extra_labels,
        )

        query.create_query_strings.append(
            f"""CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({new_node_identifier})
            SET {relation_identifier} = ${edge_properties_identifier}"""
        )
    elif isinstance(relation_to_target, ReifiedRelation):
        _, new_node_identifier, _ = build_create_node_query_object(
            typing.cast("RootNode", relation_to_target),
            query=query,
            extra_labels=["DetachDelete"],
        )
        query.create_query_strings.append(
            f"""CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({new_node_identifier})
            SET {relation_identifier} = ${edge_properties_identifier}"""
        )

    else:
        query.match_query_strings.append(
            f"""MATCH ({matched_node_identifier} {{uuid: "{typing.cast("ReferenceSetBase", relation_to_target).uuid}"}})"""
        )
        query.create_query_strings.append(
            f"""
            CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({matched_node_identifier})
            SET {relation_identifier} = ${edge_properties_identifier}"""
        )


def build_create_node_query_object(
    instance: "RootNode | ReifiedRelation | EmbeddedCreateBase",
    query: CreateQuery | UpdateQuery | None = None,
    extra_labels: list[str] | None = None,
    head_node: bool = False,
    username: str | None = "DefaultUser",
) -> tuple[CreateQuery | UpdateQuery, Identifier, uuid.UUID]:
    if not username:
        username = "DefaultUser"

    if not query:
        query = CreateQuery()

    if not extra_labels:
        extra_labels = []

    if head_node:
        extra_labels.append("HeadNode")

    node_identifier = Identifier()
    node_data_identifier = Identifier()

    instance_uuid = typing.cast(uuid.UUID, uuid7())

    if head_node:
        query.uuid = instance_uuid
        query.head_type = instance.type

    extra_node_data = {"uuid": instance_uuid, "is_deleted": False}
    if not head_node:
        extra_node_data["head_uuid"] = query.uuid
        extra_node_data["head_type"] = query.head_type

    query.query_params[node_data_identifier] = get_properties_as_writeable_dict(
        instance, extras=extra_node_data
    )

    node_labels_string = join_labels(instance.labels, extra_labels)

    query.create_query_strings.append(
        QuerySubstring(
            f"""//this |>
            CREATE ({node_identifier}:{node_labels_string})
            SET {node_identifier} += ${node_data_identifier}"""
        )
    )

    if head_node:
        user_identifier = Identifier()
        query.query_params[user_identifier] = username

        creation_node_identifier = Identifier()
        creation_data_identifier = Identifier()

        diff_from_empty = jsonpatch.JsonPatch.from_diff(
            {},
            instance.model_dump(round_trip=True, mode="json", warnings=False),
        ).to_string()

        query.query_params[creation_data_identifier] = diff_from_empty
        query.match_query_strings.append(
            f"""MATCH ({user_identifier}:PGUser {{username: ${user_identifier}}})"""
        )

        query.create_query_strings.append(
            f"""CREATE ({node_identifier})-[:PG_CREATED_IN]->({creation_node_identifier}:PGInternal:PGCore:PGCreation {{created_when: datetime.realtime('+00:00')}})-[:PG_CREATED_BY]->({user_identifier})"""
        )
        query.set_query_strings.append(
            f"""SET {creation_node_identifier}.creation = ${creation_data_identifier}"""
        )

    if head_node:
        query.return_identifier = node_identifier

    for relation_definition in instance.field_definitions.relation_fields:
        for related_instance in getattr(instance, relation_definition.field_name, []):
            build_create_relationship(
                relation_to_target=related_instance,
                relation_definition=relation_definition,
                source_node_identifier=node_identifier,
                query=query,
            )

    for embedded_definition in instance.field_definitions.embedded_fields:
        for embedded_instance in getattr(instance, embedded_definition.field_name, []):
            build_create_relationship(
                relation_to_target=embedded_instance,
                relation_definition=embedded_definition,
                source_node_identifier=node_identifier,
                query=query,
            )

    return query, node_identifier, instance_uuid
