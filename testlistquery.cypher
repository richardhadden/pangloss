CALL () {
        CALL db.index.fulltext.queryNodes("ZoteroEntryFullTextIndex", "/.*Latour.*/") YIELD node, score
        CALL (node) {
            MATCH (target:ZoteroEntry) WHERE target = node AND NOT target.is_deleted
            RETURN target
            UNION
            MATCH (target:ZoteroEntry) WHERE node.head_type = "ZoteroEntry" AND target.id=node.head_id AND NOT target.is_deleted
            RETURN target
            UNION
            MATCH (node)<-[]-(n:BaseNode)
            MATCH (target:ZoteroEntry WHERE n.head_type = "ZoteroEntry" AND target.id=n.head_id AND NOT target.is_deleted)
            RETURN target
        }
        RETURN collect(target) as target0, count(target) as c0
    }
    CALL () {
        CALL db.index.fulltext.queryNodes("ZoteroEntryFullTextIndex", "/.*Reassembling.*/") YIELD node, score
        CALL (node) {
            MATCH (target:ZoteroEntry) WHERE target = node AND NOT target.is_deleted
            RETURN target
            UNION
            MATCH (target:ZoteroEntry) WHERE node.head_type = "ZoteroEntry" AND target.id=node.head_id AND NOT target.is_deleted
            RETURN target
            UNION
            MATCH (node)<-[]-(n:BaseNode)
            MATCH (target:ZoteroEntry WHERE n.head_type = "ZoteroEntry" AND target.id=n.head_id AND NOT target.is_deleted)
            RETURN target
        }
        RETURN collect(target) as target1, count(target) as c1
    }
    CALL () {
        CALL db.index.fulltext.queryNodes("ZoteroEntryFullTextIndex", "/.*Social.*/") YIELD node, score
        CALL (node) {
            MATCH (target:ZoteroEntry) WHERE target = node AND NOT target.is_deleted
            RETURN target
            UNION
            MATCH (target:ZoteroEntry) WHERE node.head_type = "ZoteroEntry" AND target.id=node.head_id AND NOT target.is_deleted
            RETURN target
            UNION
            MATCH (node)<-[]-(n:BaseNode)
            MATCH (target:ZoteroEntry WHERE n.head_type = "ZoteroEntry" AND target.id=n.head_id AND NOT target.is_deleted)
            RETURN target
        }
        RETURN collect(target) as target2, count(target) as c2
    }
    
WITH target0, target1, target2, apoc.coll.sortMaps( [{t: target0, c: c0}, {t: target1, c: c1}, {t: target2, c: c2}], "^c") as rr
MATCH (result) WHERE result IN rr[0].t AND result IN rr[1].t AND result IN rr[2].t

WITH apoc.agg.slice(result, 0, 50) AS result, count(result) as count
RETURN {count: count, result: result }

