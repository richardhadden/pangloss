import re
import typing

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import RootNode


SPLIT_TERMS_REGEX = re.compile("[ -_]")


def build_deep_search_query(
    search_terms: list[str], node_type: str, model: "type[RootNode]"
):
    query = ""

    for i, term in enumerate(search_terms):
        query += f"""CALL () {{ CALL db.index.fulltext.queryNodes("PgIndexableNodeFullTextIndex", $q[{i}]) YIELD node, score RETURN collect(node) as n{i}, count(node) as c{i} }}\n"""

    query += f"""WITH apoc.coll.sortMaps([{", ".join(f"{{t: n{i}, c: c{i}}}" for i, _ in enumerate(search_terms))}], "^c") as FT"""

    query += f"""
    WITH FT[0].t as fullTextResultNodes, FT
    CALL (fullTextResultNodes) {{
    MATCH (t:{node_type}) WHERE t IN fullTextResultNodes AND NOT t.is_deleted
    RETURN  t
    UNION
    MATCH (t:{
        node_type
    }) WHERE any(no IN fullTextResultNodes WHERE (t.id=no.head_id OR t.head_id=no.head_id))
    RETURN  t
    {
        f'''UNION
    MATCH (x:PGIndexableNode WHERE x in fullTextResultNodes)<-[]-(no:BaseNode)
    MATCH (t:{node_type} WHERE (t.id=no.head_id OR t.head_id=no.head_id) AND NOT t.is_deleted)
    RETURN t'''
        if model._meta.fields.relation_fields or model._meta.fields.embedded_fields
        else ""
    }
    {
        f'''
    UNION
    MATCH (t:{node_type})<-[]-(ni:BaseNode) WHERE NOT t.is_deleted AND any(no IN fullTextResultNodes WHERE (ni.head_id=no.head_id OR ni.id=no.head_id OR no.id=ni.head_id OR no.head_id=ni.id))
    RETURN t'''
        if model._meta.reverse_relations
        else ""
    }
    }}"""

    for i, term in enumerate(search_terms[1:], start=1):
        query += f"""
    WITH collect(t) as currentNodes, FT, FT[{i}].t as fullTextResultNodes
    CALL (fullTextResultNodes, currentNodes) {{
    MATCH (t) WHERE NOT t.is_deleted AND t in currentNodes AND t IN fullTextResultNodes
    RETURN  t
    UNION
    MATCH (t:{
            node_type
        }) WHERE t in currentNodes AND any(no IN fullTextResultNodes WHERE (t.id=no.head_id OR t.head_id=no.head_id))   
    RETURN  t
    {
            f'''UNION
    MATCH (x:BaseNode WHERE x in fullTextResultNodes)<-[]-(no:BaseNode)
    MATCH (t:{
                node_type
            } WHERE t in currentNodes AND (t.id=no.head_id OR t.head_id=no.head_id) AND NOT t.is_deleted)
    RETURN t'''
            if model._meta.fields.relation_fields or model._meta.fields.embedded_fields
            else ""
        }
    {
            f'''UNION
    MATCH (t:{node_type})<-[]-(ni:PgIndexableNode) WHERE t in currentNodes AND NOT t.is_deleted AND any(no IN fullTextResultNodes WHERE (ni.head_id=no.head_id OR ni.id=no.head_id OR no.id=ni.head_id OR no.head_id=ni.id))
    RETURN t'''
            if model._meta.reverse_relations
            else ""
        }
    
    }}"""

    query += "WITH apoc.agg.slice(t, $skip, $skipEnd) as results, count(t) as count\n"
    query += """RETURN {count: count, page: $page, page_size: $page_size, total_pages: toInteger(round((count*1.0)/$page_size, 0, "UP")),  results: results}"""
    return query


def build_get_list_query(
    model: type["RootNode"],
    q: typing.Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    deep_search: bool = False,
) -> tuple[typing.LiteralString, dict[str, typing.Any]]:
    if q and deep_search:
        print("RUNNING DEEP SEARCH")
        """Returns a list of objects of type/subclasses of model.ReferenceView
        
        Without search param q:
             matches all items
        
        With search param q:
            split search param on space, wrap each term with regex wildcards, 
            and match against model.label using full-text index
          
        With search param q and deep_search:
            - split and wrap search params individually
            - starting with the param that produces the fewest hits, match:
                - the matched node if of the correct type
                - another node pointed to by head_id or id of matched node, if this other node is of
                    correct type
                - another node pointed to by the head_id or id of a node pointed to by the matched
                    node
                - another node pointed to by the head_id or id of a node pointing to the matched
                    node
            - take these results and pass onto the above matching strategy, *with* the condition
              that it has already been matched
            - repeat for all search terms
        """

        terms = [f"/.*{re.escape(term)}.*/" for term in SPLIT_TERMS_REGEX.split(q)]

        query = build_deep_search_query(terms, model.__name__, model)
        params = {
            "skip": (page - 1) * page_size,
            "skipEnd": (page * page_size) - 1,
            "page_size": page_size,
            "page": page,
            "q": terms,
        }

    elif q:
        print("RUNNING SHALLOW SEARCH")
        terms = SPLIT_TERMS_REGEX.split(q)

        search_string = " AND ".join(f"/.*{re.escape(term)}.*/" for term in terms)

        query = f"""            
                CALL db.index.fulltext.queryNodes("{model.__name__}FullTextIndex", $q) YIELD node, score
               
MATCH (node WHERE NOT node.is_deleted) ORDER BY score
WITH apoc.agg.slice(node, $skip, $skip_end) as results, count(node) as node_count
RETURN {{count: node_count, page_size: $page_size, page: 1, total_pages: toInteger(round((node_count*1.0)/$page_size, 0, "UP")), results: results}}
            """

        params = {
            "skip": (page - 1) * page_size,
            "skip_end": (page * page_size) - 1,
            "page_size": page_size,
            "page": page,
            "q": search_string,
        }

    else:
        print("building no search term")
        query = f"""CALL () {{
                        OPTIONAL MATCH (node:{model.__name__} WHERE NOT node.is_deleted)
                        WITH collect(node) AS ns, COUNT (DISTINCT node) as total
                        UNWIND ns AS m
                        RETURN m{{.*, uris: []}} as matches, total as total_items ORDER BY m.id DESC SKIP $skip LIMIT $pageSize
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
