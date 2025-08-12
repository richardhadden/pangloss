CALL () { CALL db.index.fulltext.queryNodes("PgIndexableNodeFullTextIndex", "/.*latour.*/") YIELD node, score RETURN collect(node) as n0, count(node) as c0 }
CALL () { CALL db.index.fulltext.queryNodes("PgIndexableNodeFullTextIndex", "/.*reassembling.*/") YIELD node, score RETURN collect(node) as n1, count(node) as c1 }
CALL () { CALL db.index.fulltext.queryNodes("PgIndexableNodeFullTextIndex", "/.*social.*/") YIELD node, score RETURN collect(node) as n2, count(node) as c2 }
WITH apoc.coll.sortMaps([{t: n0, c: c0}, {t: n1, c: c1}, {t: n2, c: c2}], "^c") as FT
    WITH FT[0].t as fullTextResultNodes, FT
    CALL (fullTextResultNodes) {
    MATCH (t:ZoteroEntry) WHERE t IN fullTextResultNodes AND NOT t.is_deleted
    RETURN  t
    UNION
    MATCH (t:ZoteroEntry) WHERE any(no IN fullTextResultNodes WHERE (t.id=no.head_id OR t.head_id=no.head_id))
    RETURN  t
    UNION
    MATCH (x:PGIndexableNode WHERE x in fullTextResultNodes)<-[]-(no:BaseNode)
    MATCH (t:ZoteroEntry WHERE (t.id=no.head_id OR t.head_id=no.head_id) AND NOT t.is_deleted)
    RETURN t
    UNION
    MATCH (t:BaseNode)<-[]-(ni:BaseNode) WHERE NOT t.is_deleted AND any(no IN fullTextResultNodes WHERE (ni.head_id=no.head_id OR ni.id=no.head_id OR no.id=ni.head_id OR no.head_id=ni.id))
    RETURN t
    }
    WITH collect(t) as currentNodes, FT, FT[1].t as fullTextResultNodes
    CALL (fullTextResultNodes, currentNodes) {
    MATCH (t) WHERE NOT t.is_deleted AND t in currentNodes AND t IN fullTextResultNodes
    RETURN  t
    UNION
    MATCH (t:ZoteroEntry) WHERE t in currentNodes AND any(no IN fullTextResultNodes WHERE (t.id=no.head_id OR t.head_id=no.head_id))   
    RETURN  t
    UNION
    MATCH (x:BaseNode WHERE x in fullTextResultNodes)<-[]-(no:BaseNode)
    MATCH (t:ZoteroEntry WHERE t in currentNodes AND (t.id=no.head_id OR t.head_id=no.head_id) AND NOT t.is_deleted)
    RETURN t
    UNION
    MATCH (t:BaseNode)<-[]-(ni:PgIndexableNode) WHERE t in currentNodes AND NOT t.is_deleted AND any(no IN fullTextResultNodes WHERE (ni.head_id=no.head_id OR ni.id=no.head_id OR no.id=ni.head_id OR no.head_id=ni.id))
    RETURN t
    }
    WITH collect(t) as currentNodes, FT, FT[2].t as fullTextResultNodes
    CALL (fullTextResultNodes, currentNodes) {
    MATCH (t) WHERE NOT t.is_deleted AND t in currentNodes AND t IN fullTextResultNodes
    RETURN  t
    UNION
    MATCH (t:ZoteroEntry) WHERE t in currentNodes AND any(no IN fullTextResultNodes WHERE (t.id=no.head_id OR t.head_id=no.head_id))   
    RETURN  t
    UNION
    MATCH (x:BaseNode WHERE x in fullTextResultNodes)<-[]-(no:BaseNode)
    MATCH (t:ZoteroEntry WHERE t in currentNodes AND (t.id=no.head_id OR t.head_id=no.head_id) AND NOT t.is_deleted)
    RETURN t
    UNION
    MATCH (t:BaseNode)<-[]-(ni:PgIndexableNode) WHERE t in currentNodes AND NOT t.is_deleted AND any(no IN fullTextResultNodes WHERE (ni.head_id=no.head_id OR ni.id=no.head_id OR no.id=ni.head_id OR no.head_id=ni.id))
    RETURN t
    }WITH apoc.agg.slice(t, 0, 49) as results, count(t) as count
RETURN {count: count, results: results}