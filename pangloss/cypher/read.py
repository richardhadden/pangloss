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
        {"OPTIONAL MATCH path_to_direct_nodes = (node)-[]->(:BaseNode)" if model.field_definitions.relation_fields else ""}
        WITH apoc.coll.flatten([
            {"collect(path_to_direct_nodes)," if model.field_definitions.relation_fields else ""}
            collect(path_to_node)
        ]) AS paths, node
        CALL apoc.convert.toTree(paths)
            YIELD value
            RETURN value as value
    """
    return typing.cast(typing.LiteralString, query), {"uuid": str(uuid)}
