# Queries for the paper

Cypher queries (Neo4j Browser, <http://localhost:7474>) and commands behind every table and figure, with the values they return on the May 2025 graph. Commands run from the main folder.

## Tables

**Conversion (`tab:conversion_results`)**
```bash
bash standalone/run_medjsonify.sh --step convert --ds 2025-05-01
cat jsonify/stats/conversion_results_2025-05-01.txt
```
Expected: converted 941 / 614 / 2,684 (total 4,239).

**Dataflow S2–S4 (`tab:dataflow`)**
```bash
bash standalone/run_medjsonify.sh --shell 'python3 /opt/airflow/dags/database/dataflow_stats.py NER/data/entities --out-dir NER/data/stats'
```
Expected S4: 2,592 drugs, 812 diseases, 51 routes, 65 years, 2,043 / 1,617 / 3,011 / 3,284 relations.

**S4 check in Neo4j** (must equal the S4 row)
```cypher
CALL { MATCH (n:Drug) RETURN count(n) AS D }
CALL { MATCH (n:Disease) RETURN count(n) AS Dis }
CALL { MATCH (n:AdminRoute) RETURN count(n) AS R }
CALL { MATCH (n:ApprovalYear) RETURN count(n) AS Y }
CALL { MATCH ()-[r:has_indication]->() RETURN count(r) AS Ind }
CALL { MATCH ()-[r:has_contraindication]->() RETURN count(r) AS CI }
CALL { MATCH ()-[r:has_administration]->() RETURN count(r) AS Adm }
CALL { MATCH ()-[r:has_approved_year]->() RETURN count(r) AS AY }
RETURN D, Dis, R, Y, Ind, CI, Adm, AY;
```

**S5a — drug–disease subnetwork and hub** (605 / 812 / 2,043 / 1,617; methylprednisolone, 69)
```cypher
MATCH (d:Drug)-[r:has_indication|has_contraindication]->(x:Disease)
WITH count(DISTINCT d) AS D, count(DISTINCT x) AS Dis,
     sum(CASE type(r) WHEN 'has_indication' THEN 1 ELSE 0 END) AS Ind,
     sum(CASE type(r) WHEN 'has_contraindication' THEN 1 ELSE 0 END) AS CI
CALL { MATCH (h:Drug)-[r:has_indication|has_contraindication]->(:Disease)
       RETURN h.name AS hub, count(r) AS hub_degree ORDER BY hub_degree DESC LIMIT 1 }
RETURN D, Dis, Ind, CI, hub, hub_degree;
```

**S5b — approval years** (2,197 drugs, 65 years, 3,284 relations; top year 2023 with 179)
```cypher
MATCH (d:Drug)-[r:has_approved_year]->(y:ApprovalYear)
RETURN count(DISTINCT d) AS D, count(DISTINCT y) AS Y, count(r) AS AY, min(y.year), max(y.year);
```

**S5c — administration routes** (2,591 drugs, 51 routes, 3,011 relations)
```cypher
MATCH (d:Drug)-[r:has_administration]->(a:AdminRoute)
RETURN count(DISTINCT d) AS D, count(DISTINCT a) AS R, count(r) AS Adm;
```

**S5d — shortest paths from ciprofloxacin** (34 drugs, 16 diseases, 81 relations)
```cypher
MATCH (s:Drug {id:'DB00537'})-[r1:has_indication]->(x:Disease)<-[r2:has_indication]-(t:Drug)
WHERE t <> s
WITH collect(DISTINCT t) AS drugs, collect(DISTINCT x) AS dis,
     collect(DISTINCT r1) + collect(DISTINCT r2) AS rels
RETURN 1 + size(drugs) AS D, size(dis) AS Dis, size(rels) AS Ind;
```

## Figures

Browser settings: `:config initialNodeDisplay: 5000`, `:config maxNeighbours: 5000`, `:config maxRows: 5000`; turn off *Connect result nodes*.
Colours: drugs purple, diseases blue, routes yellow, years pink; `has_indication` green, `has_contraindication` red, `has_administration` orange, `has_approved_year` teal.

```cypher
// Drug–disease subnetwork; inset: methylprednisolone
MATCH p = (:Drug)-[:has_indication|has_contraindication]->(:Disease) RETURN collect(p);
MATCH p = (:Drug {id:'DB00959'})-[:has_indication|has_contraindication]->(:Disease) RETURN collect(p);

// Approval-year subnetwork; inset: 2023
MATCH p = (:Drug)-[:has_approved_year]->(:ApprovalYear) RETURN collect(p);
MATCH p = (:Drug)-[:has_approved_year]->(y:ApprovalYear) WHERE y.year = 2023 RETURN collect(p);

// Shortest paths from ciprofloxacin (65 paths)
MATCH p = (s:Drug {id:'DB00537'})-[:has_indication]->(:Disease)<-[:has_indication]-(t:Drug)
WHERE t <> s RETURN p;

// Posaconazole ego network
MATCH (d:Drug) WHERE toLower(d.name) CONTAINS 'posaconazole'
MATCH (d)-[r]->(x) RETURN type(r), coalesce(x.name, toString(x.year)), x.id;
```

Charts drawn with Python (`figures/`), from these CSV exports:

```cypher
// approval_histogram.py
MATCH (d:Drug)-[:has_approved_year]->(y:ApprovalYear)
RETURN y.year AS year, count(DISTINCT d) AS drugs ORDER BY year;

// route_barchart.py
MATCH (d:Drug)-[:has_administration]->(a:AdminRoute)
RETURN a.name AS route, count(DISTINCT d) AS drugs ORDER BY drugs DESC;

// degree_barchart.py
MATCH (d:Drug)-[r:has_indication|has_contraindication]->(:Disease)
RETURN d.name AS drug, d.id AS id,
       sum(CASE type(r) WHEN 'has_indication' THEN 1 ELSE 0 END) AS indications,
       sum(CASE type(r) WHEN 'has_contraindication' THEN 1 ELSE 0 END) AS contraindications,
       count(r) AS degree ORDER BY degree DESC LIMIT 20;
```

## Use cases

**UC1 — indicated for rheumatoid arthritis, not contraindicated in asthma** (15 of 23)
```cypher
MATCH (d:Drug)-[:has_indication]->(:Disease {id:'DOID:7148'})
WHERE NOT EXISTS { (d)-[:has_contraindication]->(:Disease {id:'DOID:2841'}) }
RETURN DISTINCT d.name, d.id ORDER BY d.name;
```

**UC2 — doxycycline vs minocycline** (25 shared indications; 4 and 5 specific)
```cypher
MATCH (a:Drug {id:'DB00254'}), (b:Drug {id:'DB01017'})
MATCH (a)-[r]->(x:Disease) WHERE NOT (b)-[:has_indication|has_contraindication]->(x)
RETURN 'doxycycline only' AS side, type(r), x.name
UNION
MATCH (a:Drug {id:'DB00254'}), (b:Drug {id:'DB01017'})
MATCH (b)-[r]->(x:Disease) WHERE NOT (a)-[:has_indication|has_contraindication]->(x)
RETURN 'minocycline only' AS side, type(r), x.name;
```

**UC3 — hub audit**: the degree query above. Lactose must be absent (empty result):
```cypher
MATCH (d:Drug) WHERE d.id = 'CHEBI:17716' OR toLower(d.name) CONTAINS 'lactose' RETURN d;
```

## Validation and conversion strategies

```bash
# Hetionet (strict P 0.85, R 0.42, F1 0.56; 147 drugs)
bash standalone/run_medjsonify.sh --step export
bash standalone/run_medjsonify.sh --shell 'python3 /opt/airflow/dags/database/compare_benchmarks.py evaluate --indicated /opt/airflow/dags/database/output/indicated.csv --obo /opt/airflow/dags/database/benchmarks/doid.obo --hetionet-pairs /opt/airflow/dags/database/benchmarks/hetionet_indicated.csv --out /opt/airflow/dags/database/benchmarks/results'

# Python vs XSLT (0 failures each)
bash standalone/run_medjsonify.sh --shell 'python3 /opt/airflow/dags/jsonify/xml_strategy_comparison.py /opt/airflow/dags/jsonify/input/xml_files --xslt /opt/airflow/dags/jsonify/spl_to_json.xsl --out /opt/airflow/dags/jsonify/stats'
```