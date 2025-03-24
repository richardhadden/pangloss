import re
import typing

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import RootNode


def build_get_list_query(
    model: type["RootNode"],
    q: typing.Optional[str] = None,
    page: int = 1,
    page_size: int = 10,
    deep_search: bool = False,
) -> tuple[typing.LiteralString, dict[str, typing.Any]]:
    if q and deep_search:
        """Returns a list of objects of type/subclasses of model.ReferenceView
        
        Without search param q:
             matches all items
        
        With search param q:
            split search param on space, wrap each term with regex wildcards, 
            and match against model.label using full-text index
          
        With search param q and deep_search:
            split and wrap search params as above, match all node labels of any type,
            returning:
                - the matched node if of the correct type
                - another node pointed to by head_id of matched node, if this other node is of
                    correct type
                - another node pointed to by the head_id of a node pointed to by the matched
                    node
        """

        terms = q.split()
        search_string = " AND ".join(f"/.*{re.escape(term)}.*/" for term in terms)

        query = f"""
        CALL () {{
            CALL db.index.fulltext.queryNodes("PgIndexableNodeFullTextIndex", "origins") YIELD node, score
            CALL (node, score) {{
                MATCH (node WHERE node:{model.__name__} and not node.is_deleted)
                RETURN node as item, score * 3 as this_score
                UNION
                MATCH (item:{model.__name__})
                WHERE node.head_type = "{model.__name__}" AND item.id=node.head_id AND NOT item.is_deleted
                RETURN item, score * 2 as this_score
                UNION
                MATCH (node)<-[]-(n:BaseNode)
                MATCH (item:Factoid WHERE n.head_type = "{model.__name__}" AND item.id=n.head_id AND NOT item.is_deleted)
                RETURN item, score as this_score
            }}
            WITH DISTINCT item, max(this_score) as max_score ORDER BY max_score
            RETURN collect(item) as results, count(item) as total_items
        }}
        RETURN {{
            results: results, 
            count: total_items, 
            page: 1, 
            page_size: 10, 
            totalPages: 
            toInteger(round((total_items*1.0)/10, 0, "UP"))
        }}
        """
        params = {
            "skip": (page - 1) * page_size,
            "page_size": page_size,
            "page": page,
            "q": search_string,
        }

    elif q:
        terms = q.split(" ")

        search_string = " AND ".join(f"/.*{re.escape(term)}.*/" for term in terms)

        query = f"""            
                CALL db.index.fulltext.queryNodes("{model.__name__}FullTextIndex", $q) YIELD node, score
                WITH COLLECT {{ MATCH (node WHERE NOT node.is_deleted) RETURN DISTINCT node ORDER BY score SKIP $skip LIMIT $page_size}} AS nodes, score
                WITH collect(nodes) as nodes, count(DISTINCT nodes) as total_items
                RETURN {{results: apoc.coll.flatten(nodes), count: total_items, page_size: $page_size, page: 1, total_pages: toInteger(round((total_items*1.0)/$page_size, 0, "UP"))}}
            """

        params = {
            "skip": (page - 1) * page_size,
            "page_size": page_size,
            "page": page,
            "q": search_string,
        }

    else:
        query = f"""CALL () {{
                        MATCH (node:{model.__name__} WHERE NOT node.is_deleted)
                        WITH collect(node) AS ns, COUNT (DISTINCT node) as total
                        UNWIND ns AS m
                        RETURN m as matches, total as total_items ORDER BY m.id DESC SKIP $skip LIMIT $pageSize
                    }}
                    WITH COLLECT(matches) AS matches_list, total_items
                    RETURN {{results: matches_list, count: total_items, page: $page, page_size: $pageSize, totalPages: toInteger(round((total_items*1.0)/$pageSize, 0, "UP"))}}
                """
        params = {
            "skip": (page - 1) * page_size,
            "pageSize": page_size,
            "page": page,
        }
    return typing.cast(typing.LiteralString, query), params
