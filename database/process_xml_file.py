# Approval years from the Orange Book / Purple Book (see approval_years.py)
try:
    from database.approval_years import approval_year, parse_year
except ImportError:
    from approval_years import approval_year, parse_year

# Active ingredients that are never the therapeutic component of a product
# (e.g. the alcohol in a kit's prep pad). Keep this list short and report it in the paper.
NON_THERAPEUTIC_ACTIVES = {"WATER", "ISOPROPYL ALCOHOL"}


def process_xml_file(file_path, neo4j_handler):
    """
    Process a JSON file (derived from XML) and load data into Neo4j.

    Extracts drug and disease information (DOID, ORDO and HPO) from a JSON file,
    transforms it into the required format, and loads it into the Neo4j database.

    Drug IDs: DrugBank first, ChEBI as fallback, in every source, so that the
    same drug gets the same node whichever source it comes from.

    Approval year:
      - DailyMed: year of the FDA application (approval_id) in the Orange Book
        or Purple Book; the product's first marketing date as a fallback.
        The label's effectiveTime is a label-version date and is not used.
      - Orange Book / Purple Book: their own approval date.

    Args:
        file_path (str): Path to the JSON file
        neo4j_handler (Neo4jHandler): Handler for Neo4j database operations
    """
    try:
        data = load_json(file_path)

        if "ingredients" in data:
            # XML-derived file (DailyMed): use only ingredients marked active by the SPL
            active_ingredients = [
                ingredient for ingredient in data.get("ingredients", [])
                if (ingredient.get("class_code") or "").upper().startswith("ACT")
                and (ingredient.get("name") or "").upper() not in NON_THERAPEUTIC_ACTIVES
            ]
            if not active_ingredients:
                return

            # Diseases are the same for every active ingredient of the product
            diseases, indications, contraindications = [], [], []
            for disease_id, name in _disease_entities(data.get("indications")):
                diseases.append({"id": disease_id, "name": name})
                indications.append({"id": disease_id})
            for disease_id, name in _disease_entities(data.get("contraindications")):
                diseases.append({"id": disease_id, "name": name})
                contraindications.append({"id": disease_id})

            # Approval year of the product's FDA application (same for all its ingredients)
            year, year_source = approval_year(data.get("approval_id"),
                                              data.get("marketing_start"))

            seen = set()

            # Every active ingredient becomes a drug node (not only the first one)
            for ingredient in active_ingredients:
                chebi_id = clean_id(ingredient.get("chebi_id"))
                drugbank_id = clean_id(ingredient.get("drugbank_id"))

                # Use DrugBank ID as primary identifier, fallback to CHEBI ID
                drug_id = drugbank_id or chebi_id
                if not drug_id or drug_id in seen:
                    continue
                seen.add(drug_id)

                drug = {
                    "id": drug_id,
                    "name": ingredient.get("name"),
                    "organization": data.get("organization"),
                    "effectiveTime": data.get("effectiveTime"),
                    "admin_route": data.get("admin_route"),
                    "approval_year": year,
                    "approval_year_source": year_source,
                    "application": data.get("approval_id"),
                    "chebi_id": chebi_id,
                    "drugbank_id": drugbank_id,
                }

                print(f"Drug: {drug_id} (DrugBank: {drugbank_id}, CHEBI: {chebi_id})")
                print(f"Admin Route: {drug.get('admin_route')}, "
                      f"Approval Year: {year} ({year_source or 'not found'})")
                print(f"Found {len(diseases)} diseases, {len(indications)} indications, "
                      f"{len(contraindications)} contraindications")

                neo4j_handler.insert_data(drug, diseases, indications, contraindications)

        else:
            # Regular JSON file (Orange Book / Purple Book)
            for drug_entry in data.get("drug", []):
                chebi_id = clean_id(drug_entry.get("chebi_id"))
                drugbank_id = clean_id(drug_entry.get("drugbank_id"))

                # Use DrugBank ID as primary identifier, fallback to CHEBI ID
                # (same order as for DailyMed, so the same drug is one node)
                drug_id = drugbank_id or chebi_id
                if not drug_id:
                    continue

                # The source's own approval date (not a label date)
                approval_date = (
                    data.get("Approval_Date") or
                    data.get("Approval Date") or
                    drug_entry.get("approval_date")
                )
                # parse_year also reads the Purple Book's two-digit years ("3-Nov-03")
                approval_year_value = parse_year(approval_date)
                if approval_date and "prior to" in str(approval_date).lower():
                    approval_year_value = None      # "Approved Prior to Jan 1, 1982"
                admin_route = drug_entry.get("admin_route") or data.get("Route of Administration")

                drug = {
                    "id": drug_id,
                    "name": drug_entry.get("name"),
                    "organization": data.get("organization") or data.get("Applicant"),
                    "effectiveTime": data.get("effectiveTime"),
                    "admin_route": admin_route,
                    "approval_year": approval_year_value,
                    "approval_year_source": "orange_book" if "Approval_Date" in data else
                                            ("purple_book" if "Approval Date" in data else None),
                    "chebi_id": chebi_id,
                    "drugbank_id": drugbank_id,
                }

                diseases, indications, contraindications = [], [], []

                # Prioritize DOID, then Orphanet, then HPO
                for ind in data.get("indications", []):
                    disease_id = (clean_id(ind.get("doid_id")) or
                                  clean_id(ind.get("orphanet_id")) or
                                  clean_id(ind.get("hpo_id")))
                    if disease_id:
                        diseases.append({"id": disease_id, "name": ind.get("text", "Unknown")})
                        indications.append({"id": disease_id})

                for con in data.get("contraindications", []):
                    disease_id = (clean_id(con.get("doid_id")) or
                                  clean_id(con.get("orphanet_id")) or
                                  clean_id(con.get("hpo_id")))
                    if disease_id:
                        diseases.append({"id": disease_id, "name": con.get("text", "Unknown")})
                        contraindications.append({"id": disease_id})

                print(f"Drug: {drug_id} (DrugBank: {drugbank_id}, CHEBI: {chebi_id})")
                print(f"Admin Route: {admin_route}, Approval Year: {approval_year_value}")
                print(f"Found {len(diseases)} diseases, {len(indications)} indications, "
                      f"{len(contraindications)} contraindications")

                neo4j_handler.insert_data(drug, diseases, indications, contraindications)

    except Exception as e:
        print(f"Error processing file '{file_path}': {e}")