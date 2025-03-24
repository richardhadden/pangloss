import typing

import jsonpatch
from ulid import ULID

from pangloss.exceptions import PanglossNotFoundError
from pangloss.model_config.models_base import EditHeadSetBase, RootNode
from pangloss.neo4j.create import (
    Identifier,
    QueryObject,
    add_uri_nodes_query,
    get_properties_as_writeable_dict,
)
from pangloss.neo4j.database import Transaction, database


@database.read_transaction
async def get_existing(
    model: type[RootNode], tx: Transaction, id: ULID
) -> EditHeadSetBase:
    query = f"""
        MATCH path_to_node = (node:BaseNode {{id: $id}})
        
        OPTIONAL MATCH (node)-[:URIS]->(uris:PGUri)
       
        // Collect outgoing node patterns
        CALL (node) {{
            {"OPTIONAL MATCH path_to_direct_nodes = (node)-[{_pg_primary_rel: true}]->(:BaseNode)" if model._meta.fields.relation_fields else ""}
            {"OPTIONAL MATCH path_to_related_through_embedded = (node)-[{_pg_primary_rel: true}]->(:Embedded)((:Embedded)-[{_pg_primary_rel: true}]->(:Embedded)){ 0, }(:Embedded)-[{_pg_primary_rel: true}]->{0,}(:BaseNode)" if model._meta.fields.embedded_fields else ""}
            {"OPTIONAL MATCH path_through_read_nodes = (node)-[{_pg_primary_rel: true}]->(:ReadInline)((:ReadInline)-[{_pg_primary_rel: true}]->(:ReadInline)){0,}(:ReadInline)-[{_pg_primary_rel: true}]->{0,}(:BaseNode)" if model._meta.fields.relation_fields else ""}
            OPTIONAL MATCH path_to_reified = (node)-[{{_pg_primary_rel: true}}]->(first_reified:ReifiedRelation)((:ReifiedRelation)-[{{_pg_primary_rel: true}}]->(x WHERE x:BaseNode or x:ReifiedRelation)){{0,}}(:BaseNode)
            WITH apoc.coll.flatten([
                collect(path_to_reified),
                {"collect(path_through_read_nodes)," if model._meta.fields.relation_fields else ""}
                {"collect(path_to_related_through_embedded)," if model._meta.fields.embedded_fields else ""}
                {"collect(path_to_direct_nodes)," if model._meta.fields.relation_fields else ""}
                []
            ]) AS paths, node
            CALL apoc.paths.toJsonTree(paths)
                YIELD value
                RETURN value as outgoing 
        }}
       
        WITH node, outgoing, {{uris: collect(uris.uri)}} as all_uris

        RETURN apoc.map.mergeList([node, all_uris, outgoing])"""

    result = await tx.run(query, {"id": str(id)})
    records = await result.value()
    if records:
        return model.EditHeadSet(**records[0])
    raise PanglossNotFoundError(f"{model.__name__}")


async def build_update_query(
    instance: EditHeadSetBase,
    current_username: str = "DefaultUser",
    use_defer: bool = False,
) -> QueryObject:
    # Get existing item, and make a json update patch
    existing = await get_existing(
        typing.cast(type[RootNode], instance.__pg_base_class__), instance.id
    )
    print(instance)
    print(instance.model_dump(round_trip=False, mode="json"))
    update_json_patch = jsonpatch.JsonPatch.from_diff(
        existing.model_dump(round_trip=True, mode="json"),
        instance.model_dump(round_trip=True, mode="json"),
    )

    if not update_json_patch:
        # In this case, there is no change in the data and we can return None early
        return None

    query_object = QueryObject()
    node_identifier = Identifier()
    update_json_patch_identifier = query_object.params.add(
        update_json_patch.to_string()
    )

    query_object.return_identifier = node_identifier
    query_object.head_id = instance.id
    query_object.head_type = instance.type

    user_node_identifier = Identifier()
    head_id_identifier = query_object.params.add(str(query_object.head_id))
    node_properties = get_properties_as_writeable_dict(instance, {})

    head_node_data_identifier = query_object.params.add(node_properties)
    username_identifier = query_object.params.add(current_username)
    modification_id_identifier = query_object.params.add(str(ULID()))

    # Match THIS node first, and update the properties
    query_object.match_query_strings.append(
        f"""MATCH ({query_object.return_identifier}:BaseNode {{id: ${head_id_identifier}}})"""
    )
    query_object.set_query_strings.append(
        f"""SET {query_object.return_identifier} += ${head_node_data_identifier}"""
    )

    # Create PGModification node by diffing instance and existing; add write to query
    query_object.match_query_strings.append(
        f"""MATCH ({user_node_identifier}:PGUser {{username: ${username_identifier}}}) // Find user"""
    )

    query_object.create_query_strings.append(
        f"CREATE ({query_object.return_identifier})-[:PG_MODIFIED_IN]->(:PGInternal:PGCore:PGModification {{modified_when: datetime.realtime('+00:00'), modification: ${update_json_patch_identifier}, id: ${modification_id_identifier}}})-[:PG_MODIFIED_BY]->({user_node_identifier}) "
    )

    query_object.create_query_strings.append(
        f"""
            WITH {query_object.return_identifier}
            OPTIONAL MATCH (to_delete:PGIndexableNode {{head_id: ${head_id_identifier}}})
            DETACH DELETE to_delete
        """
    )

    add_uri_nodes_query(
        instance_uris=instance.uris,
        node_identifier=node_identifier,
        query_object=query_object,
    )

    """ for relation_definition in instance._meta.fields.relation_fields:
        for related_instance in getattr(instance, relation_definition.field_name, []):
            add_create_relation_query(
                target_instance=related_instance,
                source_instance=instance,
                relation_definition=relation_definition,
                source_node_identifier=node_identifier,
                query_object=query_object,
                source_node_id=instance.id,
                username=current_username,
            )

    for embedded_definition in instance._meta.fields.embedded_fields:
        for embedded_instance in getattr(instance, embedded_definition.field_name, []):
            add_create_relation_query(
                target_instance=embedded_instance,
                source_instance=instance,
                relation_definition=embedded_definition,
                source_node_identifier=node_identifier,
                query_object=query_object,
                source_node_id=instance.id,
                username=current_username,
            ) """

    return query_object

    # TODO: DO something about the URIs...
    # What will actually happen when we trash everything? URI nodes become disconnected
    # But then found/created and reattached!

    # and need to be connected/added again

    # Write node props updates
    # Trash all head_id == instance_id

    # Run create_relation for all options thereafter

    return query_object
