import typing

if typing.TYPE_CHECKING:
    from pangloss.model_config.models_base import RootNode


def build_get_list_query(
    model: type["RootNode"], q: typing.Optional[str], page: int = 1, page_size: int = 10
) -> tuple[str, dict]:
    query = f"""CALL {{
                        MATCH (node:{model.__name__})
                        WITH collect(node) AS ns, COUNT (DISTINCT node) as total
                        UNWIND ns AS m
                        RETURN m as matches, total as total_items ORDER BY m.uuid DESC SKIP $skip LIMIT $pageSize
                    }}
                    WITH COLLECT(matches) AS matches_list, total_items
                    RETURN {{results: matches_list, count: total_items, page: $page, totalPages: toInteger(round((total_items*1.0)/$pageSize, 0, "UP"))}}
                """
    params = {
        "skip": (page - 1) * page_size,
        "pageSize": page_size,
        "page": page,
    }
    return query, params