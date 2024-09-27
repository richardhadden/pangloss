docker run --name neo4j-pangloss-test \
    -p 7475:7474 -p 7688:7687 \
    -v $PWD/neo4j-docker/data:/data -v $PWD/neo4j-docker/plugins:/plugins \
    -e NEO4J_apoc_export_file_enabled=true \
    -e NEO4J_apoc_import_file_enabled=true \
    -e NEO4J_apoc_import_file_use__neo4j__config=true \
    -e NEO4J_PLUGINS=\[\"apoc\"\] \
    -e NEO4J_dbms_security_procedures_unrestricted=apoc.\\\* \
    neo4j:latest