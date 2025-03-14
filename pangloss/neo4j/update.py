import typing

import jsonpatch
from uuid_extensions import uuid7

from pangloss.model_config.models_base import (
    EditSetBase,
    EmbeddedCreateBase,
    EmbeddedSetBase,
    ReferenceSetBase,
    ReifiedRelation,
    RootNode,
)
from pangloss.neo4j.create import build_create_node_query_object
from pangloss.neo4j.utils import (
    Identifier,
    UpdateQuery,
    convert_dict_for_writing,
    get_properties_as_writeable_dict,
)

if typing.TYPE_CHECKING:
    from pangloss.model_config.field_definitions import (
        EmbeddedFieldDefinition,
        RelationFieldDefinition,
    )


async def create_modification_node_or_no_update(
    instance: "EditSetBase | EmbeddedSetBase",
    query: UpdateQuery,
    username: str = "DefaultUser",
) -> bool:
    from pangloss.models import BaseNode

    # Get the old edit view
    edit_view = await typing.cast(type[BaseNode], instance.base_class).get_edit_view(
        uuid=instance.uuid
    )

    # Diff the JSON dumps of values
    forward_operation = jsonpatch.JsonPatch.from_diff(
        edit_view.model_dump(round_trip=True, mode="json"),
        instance.model_dump(round_trip=True, mode="json"),
    )

    if forward_operation:
        reverse_operation_identifier = Identifier()
        reverse_operation_serialized = forward_operation.to_string()

        user_identifier = Identifier()
        modification_uuid_identifier = Identifier()
        query.query_params[user_identifier] = username

        query.match_query_strings_top.append(
            f"""MATCH ({user_identifier}:PGUser {{username: ${user_identifier}}}) // Find user"""
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

        query.query_params[edge_properties_identifier] = convert_dict_for_writing(
            edge_properties
        )

        if isinstance(related_node, (RootNode, ReifiedRelation)):
            extra_labels = ["ReadInline", "CreateInline", "DetachDelete"]
            if relation_definition.edit_inline:
                extra_labels.append("EditInline")
            create_query, related_identifier, related_uuid = (
                build_create_node_query_object(
                    related_node,
                    query,
                    extra_labels=extra_labels,
                )
            )

            query.query_params[extant_related_node_uuid_list_identifier].append(
                str(related_uuid)
            )

            query.create_query_strings.append(
                f"""
                   CREATE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({related_identifier})
                """
            )
            query.set_query_strings.append(
                f"SET {relation_identifier} = ${edge_properties_identifier}"
            )

        elif isinstance(related_node, EditSetBase) and (
            relation_definition.edit_inline
            or issubclass(related_node.base_class, ReifiedRelation)
        ):
            query, related_node_identifier, _ = await build_update_node_query_object(
                related_node, query
            )

            query.call_query_strings.append(f"""
                CALL ({source_node_identifier}) {{
                    MATCH ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({related_node_identifier})
                    SET {relation_identifier} = ${edge_properties_identifier}
                }}                                
            """)
            # query.match_query_strings.append(
            #    f"""
            #    MATCH ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({related_node_identifier})
            #    """
            # )
            # query.set_query_strings.append(
            #    f"SET {relation_identifier} = ${edge_properties_identifier}"
            # )

        elif isinstance(related_node, ReferenceSetBase):
            related_node_uuid_identifier = Identifier()
            node_to_relate_identifier = Identifier()
            query.query_params[related_node_uuid_identifier] = str(related_node.uuid)
            # Match node where it is not attached with rel and attach it

            query.match_query_strings_top.append(
                f"""
                MATCH ({node_to_relate_identifier} {{uuid: ${related_node_uuid_identifier}}})
                """
            )
            query.merge_query_strings.append(
                f"""    
                MERGE ({source_node_identifier})-[{relation_identifier}:{relation_definition.field_name.upper()}]->({node_to_relate_identifier})
                """
            )

            query.set_query_strings.append(
                f"SET {relation_identifier} += ${edge_properties_identifier}"
            )

    # From here, generate queries to clean up non-present relations
    to_delete_related_item_identifier = Identifier()
    delete_path_identifier = Identifier()

    existing_related_item_identifier = Identifier()
    existing_relation_identifier = Identifier()
    # TODO: improve performance of query
    query.match_query_strings.append(
        f"""
            OPTIONAL MATCH ({source_node_identifier})-[:{relation_definition.field_name.upper()}]->({to_delete_related_item_identifier}:DetachDelete)
            WHERE NOT {to_delete_related_item_identifier}.uuid IN ${extant_related_node_uuid_list_identifier}
            OPTIONAL MATCH {delete_path_identifier} = ({to_delete_related_item_identifier})((:DetachDelete)-->(:DetachDelete)){{0,}}(:DetachDelete)
        """
    )
    query.delete_query_strings.append(f"""        
            DETACH DELETE {to_delete_related_item_identifier}
            DETACH DELETE {delete_path_identifier}""")
    query.match_query_strings.append(f"""        
            OPTIONAL MATCH ({source_node_identifier})-[{existing_relation_identifier}:{relation_definition.field_name.upper()}]->({existing_related_item_identifier})
            WHERE NOT {existing_related_item_identifier}.uuid IN ${extant_related_node_uuid_list_identifier}
            
        """)
    query.delete_query_strings.append(f"DELETE {existing_relation_identifier}")


async def build_update_embedded_query(
    query: UpdateQuery,
    source_node_identifier: Identifier,
    embedded_nodes: list["EmbeddedSetBase | EmbeddedCreateBase"],
    embedded_definition: "EmbeddedFieldDefinition",
):
    extant_related_node_uuids = [
        str(embedded_node.uuid)
        for embedded_node in embedded_nodes
        if isinstance(embedded_node, EmbeddedSetBase)
    ]

    extant_related_node_uuid_list_identifier = Identifier()
    query.query_params[extant_related_node_uuid_list_identifier] = (
        extant_related_node_uuids
    )

    for embedded_node in embedded_nodes:
        relation_identifier = Identifier()
        if isinstance(embedded_node, EmbeddedCreateBase):
            extra_labels = ["Embedded", "DetachDelete"]

            create_query, related_identifier, related_uuid = (
                build_create_node_query_object(
                    embedded_node,
                    query,
                    extra_labels=extra_labels,
                )
            )

            query.query_params[extant_related_node_uuid_list_identifier].append(
                str(related_uuid)
            )

            query.create_query_strings.append(
                f"""
                   CREATE ({source_node_identifier})-[{relation_identifier}:{embedded_definition.field_name.upper()}]->({related_identifier})
                """
            )

        elif isinstance(embedded_node, EmbeddedSetBase):
            query, related_node_identifier, _ = await build_update_node_query_object(
                embedded_node, query
            )

            query.match_query_strings.append(
                f"""
                MATCH ({source_node_identifier})-[{relation_identifier}:{embedded_definition.field_name.upper()}]->({related_node_identifier})
                """
            )

    to_delete_related_item_identifier = Identifier()
    delete_path_identifier = Identifier()

    existing_related_item_identifier = Identifier()
    existing_relation_identifier = Identifier()

    query.match_query_strings.append(
        f"""
            OPTIONAL MATCH ({source_node_identifier})-[:{embedded_definition.field_name.upper()}]->({to_delete_related_item_identifier}:DetachDelete)
            WHERE NOT {to_delete_related_item_identifier}.uuid IN ${extant_related_node_uuid_list_identifier}
            OPTIONAL MATCH {delete_path_identifier} = ({to_delete_related_item_identifier})((:DetachDelete)-->(:DetachDelete)){{0,}}(:DetachDelete)
        """
    )
    query.delete_query_strings.append(f"""        
            DETACH DELETE {to_delete_related_item_identifier}
            DETACH DELETE {delete_path_identifier}""")
    query.match_query_strings.append(f"""        
            OPTIONAL MATCH ({source_node_identifier})-[{existing_relation_identifier}:{embedded_definition.field_name.upper()}]->({existing_related_item_identifier})
            WHERE NOT {existing_related_item_identifier}.uuid IN ${extant_related_node_uuid_list_identifier}
            
        """)
    query.delete_query_strings.append(f"DELETE {existing_relation_identifier}")


async def build_update_node_query_object(
    instance: "EditSetBase | EmbeddedSetBase",
    query: UpdateQuery | None = None,
    extra_labels: list[str] | None = None,
    head_node: bool = False,
    username: str | None = "DefaultUser",
) -> tuple[UpdateQuery, Identifier, bool]:
    if not username:
        username = "DefaultUser"

    if not query:
        query = UpdateQuery()

    node_identifier = Identifier()
    node_data_identifier = Identifier()

    if head_node:
        query.uuid = instance.uuid
        query.head_type = instance.type

    if head_node:
        query.return_identifier = node_identifier

        should_update = await create_modification_node_or_no_update(
            instance, query, username=username
        )

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
        query.match_query_strings_top.append(
            f"""MATCH ({node_identifier}:BaseNode {{uuid: ${uuid_identifier}}})
            """
        )
        query.set_query_strings.append(
            f"SET {node_identifier} += ${node_data_identifier}"
        )

    else:
        query.merge_query_strings.append(
            f"""MERGE ({node_identifier} {{uuid: ${uuid_identifier}}})
          
                
            """
        )
        query.set_query_strings.append(
            f"SET {node_identifier} += ${node_data_identifier}"
        )

    # Dispatch lists of objects for each relation field to the appropriate function
    for relation_definition in instance.field_definitions.relation_fields:
        await build_update_relation_query(
            query=query,
            source_node_identifier=node_identifier,
            related_nodes=getattr(instance, relation_definition.field_name, []),
            relation_definition=relation_definition,
        )

    for embedded_definition in instance.field_definitions.embedded_fields:
        await build_update_embedded_query(
            query=query,
            source_node_identifier=node_identifier,
            embedded_nodes=getattr(instance, embedded_definition.field_name, []),
            embedded_definition=embedded_definition,
        )

    return query, node_identifier, True
