import typing
import uuid

if typing.TYPE_CHECKING:
    from pangloss.models import BaseNode


def build_view_read_query(
    model: type["BaseNode"], uuid: uuid.UUID | str
) -> tuple[typing.LiteralString, dict[str, str]]:
    has_relation_fields = bool(model.field_definitions.relation_fields)
    has_embedded_fields = bool(model.field_definitions.embedded_fields)

    query = f"""
        MATCH path_to_node = (node:BaseNode {{uuid: $uuid}})
        
        MATCH (headnode:HeadNode)
        WHERE node = headnode OR headnode.uuid = node.head_uuid
        
        CALL (headnode, node) {{
            OPTIONAL MATCH (headnode)-[:PG_CREATED_IN]->(c:PGCreation)-[:PG_CREATED_BY]->(user:PGUser)
            RETURN 
                CASE 
                    WHEN exists((headnode)-[:PG_CREATED_IN]->(c:PGCreation)-[:PG_CREATED_BY]->(user:PGUser)) THEN {{created_when: c.created_when, created_by: user.username}}
                    ELSE {{created_when: node.created_when, created_by: node.created_by}} END
                AS creation
        }}
        
        CALL (headnode, node) {{
            OPTIONAL MATCH (headnode)-[:PG_MODIFIED_IN]->(m:PGModification)-[:PG_MODIFIED_BY]->(user:PGUser)
            ORDER BY m.modified_when DESC LIMIT 1
            RETURN 
                CASE 
                    WHEN exists((headnode)-[:PG_MODIFIED_IN]->(m:PGModification)-[:PG_MODIFIED_BY]->(user:PGUser)) THEN {{modified_when: m.modified_when, modified_by: user.username}}
                    
                ELSE {{modified_when: node.modified_when, modified_by: node.modified_by}} END
                AS modification
        }}
     
        // Collect outgoing node patterns
        CALL (node) {{
            {"OPTIONAL MATCH path_to_direct_nodes = (node)-[]->(:BaseNode)" if has_relation_fields else ""}
            {"OPTIONAL MATCH path_to_related_through_embedded = (node)-[]->(:Embedded)((:Embedded)-[]->(:Embedded)){ 0, }(:Embedded)-[]->{0,}(:BaseNode)" if has_embedded_fields else ""}
            {"OPTIONAL MATCH path_through_read_nodes = (node)-[]->(:ReadInline)((:ReadInline)-[]->(:ReadInline)){0,}(:ReadInline)-[]->{0,}(:BaseNode)" if has_relation_fields else ""}
            {"""OPTIONAL MATCH path_to_reified = (node)-[]->(first_reified:ReifiedRelation)((:ReifiedRelation)-[]->(x WHERE x:BaseNode or x:ReifiedRelation)){0,}(base_node:BaseNode)
            ORDER BY first_reified.uuid, base_node.uuid""" if has_relation_fields else ""}
            WITH apoc.coll.flatten([
                {"collect(path_to_reified)," if has_relation_fields else ""}
                {"collect(path_through_read_nodes)," if has_relation_fields else ""}
                {"collect(path_to_related_through_embedded)," if has_embedded_fields else ""}
                {"collect(path_to_direct_nodes)," if has_relation_fields else ""}
                []
            ]) AS paths, node
            CALL apoc.paths.toJsonTree(paths)
                YIELD value
                RETURN value as outgoing 
        }}
        {""" 
            CALL (node) { // Gets full context from incoming reified chain
                OPTIONAL MATCH  paths = (node)<-[to_node]-(x WHERE (x:ReifiedRelation))(()<--()){1, }()<-[reverse_relation]-(related_nodes:BaseNode)
                WITH [x in relationships(paths) WHERE type(x) <> "TARGET" | x][0].reverse_name as reverse_bind, reverse_relation, paths, related_nodes, to_node
                OPTIONAL MATCH path_down = (related_nodes)-[rr WHERE type(rr) = type(reverse_relation)]->()(()-[]->()){0,}(other_node1:BaseNode)
                WITH collect(path_down) as paths_down, paths, reverse_bind, to_node
                CALL apoc.paths.toJsonTree(paths_down) YIELD value
                WITH collect(apoc.map.mergeList([value, {edge_properties: to_node}, { __bind: reverse_bind}])) as items
                RETURN apoc.map.groupByMulti(items, "__bind") as through_reified_chain
            }
            CALL {
                WITH node
                OPTIONAL MATCH (node)<-[reverse_relation]-(x WHERE (x:Embedded))(()<--()){ 0, }()<--(related_node)
                WHERE NOT related_node:Embedded AND NOT related_node:ReifiedRelation
                WITH reverse_relation.reverse_name AS reverse_relation_type, collect(related_node) AS related_node_data
                WITH collect({ t: reverse_relation_type, related_node_data: related_node_data }) AS via_embedded
                RETURN REDUCE(s = { }, item IN apoc.coll.flatten([via_embedded]) | apoc.map.setEntry(s, item.t, item.related_node_data)) AS via_embedded

            }
             CALL (node) { // Gets basic reverse relation from incoming
                WITH node
                OPTIONAL MATCH (node)<-[reverse_relation]-(related_node:BaseNode)
                WHERE NOT related_node:Embedded AND NOT related_node:ReifiedRelation
                WITH reverse_relation.reverse_name AS reverse_relation_type, collect(related_node) AS related_node_data
                WITH collect({ t: reverse_relation_type, related_node_data: related_node_data }) AS direct_incoming
                RETURN REDUCE(s = { }, item IN apoc.coll.flatten([direct_incoming]) | apoc.map.setEntry(s, item.t, item.related_node_data)) AS reverse_relations
            }
            
        """ if model.incoming_relation_definitions else ""}
        WITH node, outgoing, modification, creation{", via_embedded, reverse_relations, through_reified_chain" if model.incoming_relation_definitions else ""}

        RETURN apoc.map.mergeList([node, creation, outgoing, modification{", via_embedded, reverse_relations, through_reified_chain" if model.incoming_relation_definitions else ""}])
    """
    return typing.cast(typing.LiteralString, query), {"uuid": str(uuid)}


def build_edit_view_query(
    model: type["BaseNode"], uuid: uuid.UUID | str
) -> tuple[typing.LiteralString, dict[str, str]]:
    query = f"""
        MATCH path_to_node = (node:BaseNode {{uuid: $uuid}})
        
        MATCH (headnode:HeadNode)
        WHERE node = headnode OR headnode.uuid = node._head_uuid
        CALL (headnode) {{
            OPTIONAL MATCH (headnode)-[:PG_CREATED_IN]->(c:PGCreation)-[:PG_CREATED_BY]->(user:PGUser)
            RETURN 
                CASE 
                    WHEN exists((headnode)-[:PG_CREATED_IN]->(c:PGCreation)-[:PG_CREATED_BY]->(user:PGUser)) THEN {{created_when: c.created_when, created_by: user.username}}
                    ELSE {{created_when: headnode.created_when, created_by: headnode.created_by}} END
                AS creation
        }}
        
        CALL (headnode) {{
            OPTIONAL MATCH (headnode)-[:PG_MODIFIED_IN]->(m:PGModification)-[:PG_MODIFIED_BY]->(user:PGUser)
            ORDER BY m.modified_when DESC LIMIT 1
            RETURN 
                CASE 
                    WHEN exists((headnode)-[:PG_MODIFIED_IN]->(m:PGModification)-[:PG_MODIFIED_BY]->(user:PGUser)) THEN {{modified_when: m.modified_when, modified_by: user.username}}
                    
                ELSE {{modified_when: headnode.modified_when, modified_by: headnode.modified_by}} END
                AS modification
        }}
     
        // Collect outgoing node patterns
        CALL (node) {{
            {"OPTIONAL MATCH path_to_direct_nodes = (node)-[]->(:BaseNode)" if model.field_definitions.relation_fields else ""}
            {"OPTIONAL MATCH path_to_related_through_embedded = (node)-[]->(:Embedded)((:Embedded)-[]->(:Embedded)){ 0, }(:Embedded)-[]->{0,}(:BaseNode)" if model.field_definitions.embedded_fields else ""}
            {"OPTIONAL MATCH path_through_read_nodes = (node)-[]->(:ReadInline)((:ReadInline)-[]->(:ReadInline)){0,}(:ReadInline)-[]->{0,}(:BaseNode)" if model.field_definitions.relation_fields else ""}
            OPTIONAL MATCH path_to_reified = (node)-[]->(first_reified:ReifiedRelation)((:ReifiedRelation)-[]->(x WHERE x:BaseNode or x:ReifiedRelation)){{0,}}(:BaseNode)
            WITH apoc.coll.flatten([
                collect(path_to_reified),
                {"collect(path_through_read_nodes)," if model.field_definitions.relation_fields else ""}
                {"collect(path_to_related_through_embedded)," if model.field_definitions.embedded_fields else ""}
                {"collect(path_to_direct_nodes)," if model.field_definitions.relation_fields else ""}
                []
            ]) AS paths, node
            CALL apoc.paths.toJsonTree(paths)
                YIELD value
                RETURN value as outgoing 
        }}
       
        WITH node, outgoing, modification, creation

        RETURN apoc.map.mergeList([node, creation, outgoing, modification])
    """
    return typing.cast(typing.LiteralString, query), {"uuid": str(uuid)}
