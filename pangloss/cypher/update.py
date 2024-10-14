import typing

from patchdiff import diff
from patchdiff.pointer import Pointer
from uuid_extensions import uuid7

from pangloss.cypher.utils import (
    UpdateQuery,
    Identifier,
    get_properties_as_writeable_dict,
)

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import EditSetBase, ReferenceSetBase
    from pangloss.model_config.field_definitions import RelationFieldDefinition

    Pointer  # type: ignore


async def create_modification_node(
    instance: "EditSetBase", query: UpdateQuery, user: str = "DefaultUser"
) -> bool:
    from pangloss.models import BaseNode

    # Get the old edit view
    edit_view = await typing.cast(type[BaseNode], instance.base_class).get_edit_view(
        uuid=instance.uuid
    )

    # Diff the object
    _, reverse_ops = diff(dict(edit_view), dict(instance))

    if reverse_ops:
        reverse_operation_identifier = Identifier()
        reverse_operation_serialized = str(reverse_ops)

        user_identifier = Identifier()
        modification_uuid_identifier = Identifier()
        query.match_query_strings.append(
            f"""MATCH ({user_identifier}:PGUser {{username: "{user}"}})"""
        )

        query.create_query_strings.append(
            f"CREATE ({query.return_identifier})-[:PG_MODIFIED_IN]->(:PGInternal:PGCore:PGModification {{modified_when: datetime.realtime('+00:00'), modification: ${reverse_operation_identifier}, uuid: ${modification_uuid_identifier}}})-[:PG_MODIFIED_BY]->({user_identifier})"
        )
        query.query_params[reverse_operation_identifier] = reverse_operation_serialized
        query.query_params[modification_uuid_identifier] = str(uuid7())

        return True

    return False


def build_update_relation_query(
    query: UpdateQuery,
    field_name: str,
    source_node_identifier: Identifier,
    related_nodes: list["ReferenceSetBase | EditSetBase"],
    relation_definition: "RelationFieldDefinition",
):
    from pangloss.model_config.models_base import ReferenceSetBase

    extant_related_node_uuids = [
        str(related_node.uuid)
        for related_node in related_nodes
        if hasattr(related_node, "uuid")
    ]
    extant_related_node_uuid_list_identifier = Identifier()
    query.query_params[extant_related_node_uuid_list_identifier] = (
        extant_related_node_uuids
    )

    if relation_definition.edit_inline:
        pass  # do inline update
    else:
        for related_node in related_nodes:
            if isinstance(related_node, ReferenceSetBase):
                related_node_uuid_identifier = Identifier()
                node_to_relate_identifier = Identifier()
                query.query_params[related_node_uuid_identifier] = str(
                    related_node.uuid
                )
                # Match node where it is not attached with rel and attach it
                query.match_query_strings.append(
                    f"""
                
                    MATCH ({node_to_relate_identifier} {{uuid: ${related_node_uuid_identifier}}})
                    WHERE NOT ({source_node_identifier})-[:{relation_definition.field_name.upper()}]->({node_to_relate_identifier})"""
                )
                query.create_query_strings.append(
                    f"""CREATE ({source_node_identifier})-[:{relation_definition.field_name.upper()}]->({node_to_relate_identifier})"""
                )

    currently_related_item_identifier = Identifier()
    existing_rels_to_delete_identifier = Identifier()
    query.match_query_strings.append(
        f"""
      
            MATCH ({source_node_identifier})-[{existing_rels_to_delete_identifier}:{relation_definition.field_name.upper()}]->({currently_related_item_identifier})
            WHERE NOT {currently_related_item_identifier}.uuid IN ${extant_related_node_uuid_list_identifier}
            
                 
        """
    )
    query.delete_query_strings.append(f"DELETE {existing_rels_to_delete_identifier} ")


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
        query.return_identifier = node_identifier
        should_update = await create_modification_node(instance, query)
        if not should_update:
            return query, node_identifier, should_update

    uuid_identifier = Identifier()
    query.query_params[uuid_identifier] = str(instance.uuid)
    query.query_params[node_data_identifier] = query.query_params[
        node_data_identifier
    ] = get_properties_as_writeable_dict(
        instance, extras={"uuid": instance.uuid, "label": instance.label}
    )

    query.match_query_strings.append(
        f"""MATCH ({node_identifier}:BaseNode {{uuid: ${uuid_identifier}}})"""
    )
    query.set_query_strings.append(f"""SET {node_identifier} = ${node_data_identifier}
        """)

    # Dispatch lists of objects for each relation field to the appropriate function
    for relation_definition in instance.field_definitions.relation_fields:
        build_update_relation_query(
            query=query,
            field_name=relation_definition.field_name,
            source_node_identifier=node_identifier,
            related_nodes=getattr(instance, relation_definition.field_name, []),
            relation_definition=relation_definition,
        )

    return query, node_identifier, should_update
