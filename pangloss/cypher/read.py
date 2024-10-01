import typing
import uuid

if typing.TYPE_CHECKING:
    from pangloss.models import BaseNode


def build_view_read_query(
    model: type["BaseNode"], uuid: uuid.UUID | str
) -> tuple[typing.LiteralString, dict[str, str]]:
    label = model.__name__
    query = f"""
        MATCH path_to_node = (node:{label} {{uuid: $uuid}})
        MATCH (node)-[:PG_CREATED_IN]->(creation:PGCreation)-[:PG_CREATED_BY]->(user:PGUser)
        
        CALL () {{
            OPTIONAL MATCH (node)-[:PG_MODIFIED_IN]->(modification:PGModification)-[:PG_MODIFIED_BY]->(user:PGUser)
            RETURN {{modified_by: user.username, modified_when: modification.modified_when}} as modification
            ORDER BY modification.modified_when 
            LIMIT 1
        }}
        
        // Collect outgoing node patterns
        CALL (node) {{
            {"OPTIONAL MATCH path_to_direct_nodes = (node)-[]->(:BaseNode)" if model.field_definitions.relation_fields else ""}
            OPTIONAL MATCH path_through_read_nodes = (node)-[]->(:ReadInline)((:ReadInline)-[]->(:ReadInline)){{0,}}(:ReadInline)-[]->{{0,}}(:BaseNode)
            WITH apoc.coll.flatten([
                collect(path_through_read_nodes),
                {"collect(path_to_direct_nodes)," if model.field_definitions.relation_fields else ""}
                []
            ]) AS paths, node
            CALL apoc.paths.toJsonTree(paths)
                YIELD value
                RETURN value as outgoing 
        }}
        
        RETURN apoc.map.mergeList([node{{.*, created_by: user.username, created_when: creation.created_when}}, outgoing, modification])
    """
    return typing.cast(typing.LiteralString, query), {"uuid": str(uuid)}


#
