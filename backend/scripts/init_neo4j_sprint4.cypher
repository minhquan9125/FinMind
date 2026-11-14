CREATE CONSTRAINT sprint4_graph_version_id IF NOT EXISTS FOR (v:GraphVersion) REQUIRE v.id IS UNIQUE;
CREATE CONSTRAINT sprint4_graph_batch_key IF NOT EXISTS FOR (b:GraphBatch) REQUIRE b.key IS UNIQUE;
CREATE CONSTRAINT sprint4_graph_entity_key IF NOT EXISTS FOR (e:GraphEntity) REQUIRE e.key IS UNIQUE;
CREATE CONSTRAINT sprint4_graph_relation_key IF NOT EXISTS FOR ()-[r:GRAPH_RELATION]-() REQUIRE r.key IS UNIQUE;
CREATE INDEX sprint4_company_scope IF NOT EXISTS FOR (e:Company) ON (e.graph_version_id, e.entity_id);
CREATE INDEX sprint4_person_scope IF NOT EXISTS FOR (e:Person) ON (e.graph_version_id, e.entity_id);
CREATE INDEX sprint4_event_scope IF NOT EXISTS FOR (e:Event) ON (e.graph_version_id, e.entity_id);
CREATE INDEX sprint4_relation_scope IF NOT EXISTS FOR ()-[r:GRAPH_RELATION]-() ON (r.graph_version_id, r.relation_type);
