CALL () { CALL db.index.fulltext.queryNodes("PgIndexableNodeFullTextIndex", "/.*maximilian.*/") YIELD node, score RETURN collect(node) as n0, count(node) as c0 }
WITH apoc.coll.sortMaps([{t: n0, c: c0}], "^c") as FT
    WITH FT[0].t as fullTextResultNodes, FT
    CALL (fullTextResultNodes) {
    MATCH p = (t:ZoteroEntry)-[]->(:ReadInline)((:ReadInline)-[]->(:ReadInline))(0,)(:ReadInline)-[]->(0,)(:BaseNode)
    WHERE any(n in nodes(p) WHERE n in fullTextResultNodes)
    RETURN t
    }WITH apoc.agg.slice(t, 0, 49) as results, count(t) as count
RETURN {count: count, results: results}