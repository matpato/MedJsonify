# Design decisions (paper revision, October 2026)

Changes made after inspecting the results of the May 2025 run. Queries and expected values: `standalone/dataflow_queries.md`.

## Data and conversion
- DailyMed: human prescription labels of the monthly update; one label per product name (1,645 → 941).
- Purple Book: only the full product list is kept; the change report and empty rows are removed (`jsonify/purple_book.py`).
- Orange Book: only `products.txt`; one record per active ingredient.
- jsonifyer converter patched: attribute pairs (`@classCode`) and full element text (titles with markup).
- Python vs XSLT on the same 1,645 labels: no failures with either; XSLT faster. Python kept for flexibility.

## Entity linking
- Only active ingredients (SPL class code `ACT*`) become drugs; water and isopropyl alcohol excluded. Removes excipients such as lactose.
- Drugs: DrugBank by UNII, then exact name/synonym, name without salt words, fuzzy (Jaro–Winkler ≥ 0.88); ChEBI as fallback.
- Diseases: DO → Orphanet → HPO, longest match per span; HPO limited to *Phenotypic abnormality*; Orphanet/HPO mapped to DO when equivalent.
- Indications: negated statements, at-risk populations and organism names handled before linking.

## Graph
- Relations: `has_indication`, `has_contraindication`, `has_administration`, `has_approved_year`.
- Approval year from the FDA application (Orange Book / Purple Book); no year for products approved before 1982; label revision dates not used.
- Routes normalized to one node each (51 routes).
- Ontology cleanup: generic terms (DOID:4, DOID:225, …), non-disease terms, and single-word mentions of ≤ 4 characters unless a disease word; each disease keeps its longest mention.
- Export leaves out pairs that are both indicated and contraindicated.

## Analysis
- Distributions shown as charts (approval-year histogram, route and degree bar charts); node–link views for ego networks, paths and hubs.
- Shortest paths use `has_indication` only.
- Validation against Hetionet (indications): strict P 0.85, R 0.42, F1 0.56 over 147 drugs.

## Known limitations
- Co-medication restrictions linked as contraindications; causes of a treated condition linked as indications.
- Combination products: indications attached to every active ingredient.
- Short-mention rule also removes correct acronyms (e.g. ptsd).
- jsonifyer's `repeated` list numbers new records from `record_1`, overwriting earlier files.