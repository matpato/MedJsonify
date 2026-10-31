# Test sample

A small extract of the May 2025 data that runs through the whole pipeline in a few minutes, with the output it must produce. Use it to check an installation or a code change. The counts reported in the paper come from the full May 2025 release, not from this sample.

## Contents

| Folder / file | What it holds |
|---|---|
| `input/xml_files/` | 50 DailyMed labels (FDA, public domain) |
| `input/txt_files/products.txt` | 375 Orange Book rows |
| `input/csv_files/` | 64 Purple Book rows (full product list format) |
| `SAMPLE_CONTENTS.md` | Which labels and rows were chosen, and why |
| `make_sample.py` | Script that built the sample from the full input |
| `expected/` | Conversion table, dataflow counts, NER output and ontology versions of the reference run |

The labels cover every drug discussed in the paper: ciprofloxacin (shortest paths), posaconazole (ego network), doxycycline and minocycline (UC2), the NSAIDs and misoprostol (UC1), the corticosteroid hubs, sodium bicarbonate (combination product), lidocaine and dexamethasone (several routes), and one label with lactose as an inactive ingredient (excipient filter).

## Run it

In a fresh clone (not in a folder holding other data):

```bash
git clone https://github.com/matpato/MedJsonify.git
cd MedJsonify
cp -r sample/input/* jsonify/input/
mkdir -p jsonify/data NER/ontologies/data

bash standalone/run_medjsonify.sh --step convert
bash standalone/run_medjsonify.sh --step ontologies
bash standalone/run_medjsonify.sh --step vocabulary
bash standalone/run_medjsonify.sh --step preprocess
bash standalone/run_medjsonify.sh --step ner
bash standalone/run_medjsonify.sh --shell 'python3 /opt/airflow/dags/database/dataflow_stats.py NER/data/entities --out-dir NER/data/stats'
```

Then compare:

```bash
cat jsonify/output/stats/conversion_results_*.txt   # with expected/conversion_results_*.txt
cat NER/data/stats/dataflow_s2_s4.txt               # with expected/dataflow_s2_s4.txt
```

The graph step (`--step graph`) is optional: it loads Neo4j, so run it only on a Neo4j instance that holds no other graph.

## Expected results

Conversion:

| Source | Records | Duplicates | Converted |
|---|---|---|---|
| DailyMed (XML) | 50 | 12 | 38 |
| Purple Book (CSV) | 64 | 52 | 12 |
| Orange Book (TXT) | 375 | 328 | 47 |
| Total | 489 | 392 | 97 |

No record is out of scope or malformed, and every eligible record is converted.

Entities and relations (D drugs, Dis diseases, R routes, Y approval years; Ind, CI, Adm, AY relations):

| Stage | D | Dis | R | Y | Ind | CI | Adm | AY |
|---|---|---|---|---|---|---|---|---|
| S2 After NER and entity linking | 139 | 183 | 13 | 43 | 2,514 | 601 | 181 | 320 |
| S3 After active-ingredient filtering | 48 | 183 | 13 | 43 | 400 | 97 | 71 | 82 |
| S4 After ontology cleanup | 48 | 173 | 13 | 43 | 372 | 78 | 71 | 82 |

These values hold for the ontology and DrugBank versions in `expected/*_version.txt`. With newer releases (the ontologies step downloads the latest by default) the disease counts can differ slightly; the conversion counts do not depend on them.