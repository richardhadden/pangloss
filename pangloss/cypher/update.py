import typing

import jsonpatch
from uuid_extensions import uuid7
from pangloss.cypher.create import build_create_node_query_object
from pangloss.cypher.utils import (
    UpdateQuery,
    Identifier,
    convert_dict_for_writing,
    get_properties_as_writeable_dict,
)

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import EditSetBase, ReferenceSetBase
    from pangloss.model_config.field_definitions import RelationFieldDefinition


async def create_modification_node_or_no_update(
    instance: "EditSetBase", query: UpdateQuery, user: str = "DefaultUser"
) -> bool:
    from pangloss.models import BaseNode

    # Get the old edit view
    edit_view = await typing.cast(type[BaseNode], instance.base_class).get_edit_view(
        uuid=instance.uuid
    )

    # Diff the JSON dumps of values
    reverse_operation = jsonpatch.JsonPatch.from_diff(
        instance.model_dump(round_trip=True, mode="json"),
        edit_view.model_dump(round_trip=True, mode="json"),
    )

    if reverse_operation:
        reverse_operation_identifier = Identifier()
        reverse_operation_serialized = str(reverse_operation)

        user_identifier = Identifier()
        modification_uuid_identifier = Identifier()
        query.match_query_strings.append(
            f"""MATCH ({user_identifier}:PGUser {{username: "{user}"}}) // Find user"""
        )

        query.create_query_strings.append(
            f"CREATE ({query.return_identifier})-[:PG_MODIFIED_IN]->(:PGInternal:PGCore:PGModification {{modified_when: datetime.realtime('+00:00'), modification: ${reverse_operation_identifier}, uuid: ${modification_uuid_identifier}}})-[:PG_MODIFIED_BY]->({user_identifier}) "
        )
        query.query_params[reverse_operation_identifier] = reverse_operation_serialized
        query.query_params[modification_uuid_identifier] = str(uuid7())

        return True

    return False


async def build_update_relation_query(
    query: UpdateQuery,
    source_node_identifier: Identifier,
    related_nodes: list["ReferenceSetBase | EditSetBase"],
    relation_definition: "RelationFieldDefinition",
):
    from pangloss.model_config.models_base import (
        ReferenceSetBase,
        ReifiedRelation,
        EditSetBase,
        RootNode,
    )

    extant_related_node_uuids = [
        str(related_node.uuid)
        for related_node in related_nodes
        if hasattr(related_node, "uuid")
    ]

    extant_related_node_uuid_list_identifier = Identifier()
    query.query_params[extant_related_node_uuid_list_identifier] = (
        extant_related_node_uuids
    )

    edge_properties = {}

    for related_node in related_nodes:
        relation_identifier = Identifier()
        if relation_definition.field_metatype == "Relation":
            edge_properties.update(
                {
                    "reverse_name": relation_definition.reverse_name,
                    "relation_labels": relation_definition.relation_labels,
                    "reverse_relation_labels": relation_definition.reverse_relation_labels,
                }
            )

        edge_properties = convert_dict_for_writing(edge_properties)

        edge_properties_identifier = Identifier()

        if hasattr(related_node, "edge_properties"):
            edge_properties.update(related_node.edge_properties)  # type: ignore

        query.query_params[edge_properties_identifier] = edge_properties

        print(
            related_node.__class__.__name__,
            query.query_params[edge_properties_identifier],
        )

        if isinstance(related_node, (RootNode, ReifiedRelation)):
            create_query, related_identifier, related_uuid = (
                build_create_node_query_object(
                    related_node,
                    query,
                    extra_labels=["DetachDelete"],
                )
            )

            query.query_params[extant_related_node_uuid_list_identifier].append(
                str(related_uuid)
            )

            query.create_query_strings.append(
                f"""
                   CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({related_identifier})
                     SET {relation_identifier} = ${edge_properties_identifier}
                
                """
            )

        elif isinstance(related_node, EditSetBase) and (
            relation_definition.edit_inline
            or issubclass(related_node.base_class, ReifiedRelation)
        ):
            query, related_node_identifier, _ = await build_update_node_query_object(
                related_node, query
            )

            query.match_query_strings.append(
                f"""WITH *
                    MATCH ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({related_node_identifier})
                    SET {relation_identifier} = ${edge_properties_identifier}       
                """
            )

        elif isinstance(related_node, ReferenceSetBase):
            related_node_uuid_identifier = Identifier()
            node_to_relate_identifier = Identifier()
            query.query_params[related_node_uuid_identifier] = str(related_node.uuid)
            # Match node where it is not attached with rel and attach it
            query.call_query_strings.append(
                f"""CALL ({source_node_identifier}) {{
                    MATCH ({node_to_relate_identifier} {{uuid: ${related_node_uuid_identifier}}})
                    WHERE NOT ({source_node_identifier})-[:{relation_definition.field_name.upper()}]->({node_to_relate_identifier})
                    CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({node_to_relate_identifier})
                    SET {relation_identifier} = ${edge_properties_identifier}
                }}"""
            )
            query.call_query_strings.append(
                f"""CALL ({source_node_identifier}) {{
                    MATCH ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({node_to_relate_identifier})
                    SET {relation_identifier} = ${edge_properties_identifier}
                }}"""
            )

    query.call_query_strings.append(
        f"""CALL ({source_node_identifier}) {{
            OPTIONAL MATCH ({source_node_identifier})-[existing_rel:{relation_definition.field_name.upper()}]->(related_item:DetachDelete)
            WHERE NOT related_item.uuid IN ${extant_related_node_uuid_list_identifier}
            OPTIONAL MATCH delete_path = (related_item)((:DetachDelete)-->(:DetachDelete)){{0,}}(:DetachDelete)
            DETACH DELETE related_item
            DETACH DELETE delete_path
            
            WITH {source_node_identifier}
            MATCH ({source_node_identifier})-[existing_rel:{relation_definition.field_name.upper()}]->(related_item)
            WHERE NOT related_item.uuid IN ${extant_related_node_uuid_list_identifier}
            DELETE existing_rel
        }}"""
    )


async def build_update_node_query_object(
    instance: "EditSetBase",
    query: UpdateQuery | None = None,
    extra_labels: list[str] | None = None,
    head_node: bool = False,
    user: str = "DefaultUser",
) -> tuple[UpdateQuery, Identifier, bool]:
    if not query:
        query = UpdateQuery()

    node_identifier = Identifier()
    node_data_identifier = Identifier()

    if head_node:
        query.uuid = instance.uuid
        query.head_type = instance.type

    if head_node:
        query.return_identifier = node_identifier
        should_update = await create_modification_node_or_no_update(instance, query)
        if not should_update:
            return query, node_identifier, should_update

    extra_data = {"uuid": instance.uuid, "head_type": None}

    if label := getattr(instance, "label", None):
        extra_data["label"] = label

    if not head_node:
        extra_data["head_uuid"] = query.uuid
        extra_data["head_type"] = query.head_type

    uuid_identifier = Identifier()
    query.query_params[uuid_identifier] = str(instance.uuid)
    query.query_params[node_data_identifier] = get_properties_as_writeable_dict(
        instance, extras=extra_data
    )

    if head_node:
        query.match_query_strings.append(
            f"""MATCH ({node_identifier}:BaseNode {{uuid: ${uuid_identifier}}})
            SET {node_identifier} += ${node_data_identifier}"""
        )

    else:
        query.merge_query_strings.append(
            f"""MERGE ({node_identifier} {{uuid: ${uuid_identifier}}})
            ON MATCH 
                SET {node_identifier} += ${node_data_identifier}
            ON CREATE
                SET {node_identifier} += ${node_data_identifier}
            """
        )

    # Dispatch lists of objects for each relation field to the appropriate function
    for relation_definition in instance.field_definitions.relation_fields:
        await build_update_relation_query(
            query=query,
            source_node_identifier=node_identifier,
            related_nodes=getattr(instance, relation_definition.field_name, []),
            relation_definition=relation_definition,
        )

    return query, node_identifier, True