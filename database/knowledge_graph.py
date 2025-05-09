import json
import os
from neo4j import GraphDatabase
from datetime import datetime

class Neo4jHandler:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # -------------------------------------------------------------------------------------------- #

    def close(self):
        self.driver.close()

    # -------------------------------------------------------------------------------------------- #
    
    def create_constraints(self):
        with self.driver.session() as session:
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (d:Drug) ASSERT d.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (disease:Disease) ASSERT disease.id IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (r:AdminRoute) ASSERT r.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (y:ApprovalYear) ASSERT y.year IS UNIQUE") 

    # -------------------------------------------------------------------------------------------- #

    def create_drug(self, drug):
        query = """
        MERGE (d:Drug {id: $id})
        SET d.name = $name, d.organization = $organization, d.effectiveTime = $effectiveTime
        """
        with self.driver.session() as session:
            session.run(query, **drug)

    # -------------------------------------------------------------------------------------------- #

    def create_disease(self, disease):
        query = """
        MERGE (d:Disease {id: $id})
        SET d.name = $name
        """
        with self.driver.session() as session:
            session.run(query, **disease)
    
    # -------------------------------------------------------------------------------------------- #

    def create_admin_route(self, route):
        if not route:
            return
        routes = [r.strip() for r in route.split(",")] 
        with self.driver.session() as session:
            for r in routes:
                query = """
                MERGE (r:AdminRoute {name: $route})
                """
                session.run(query, route=r)

    # -------------------------------------------------------------------------------------------- #

    def create_approval_year(self, year):
        if not year:
            return
        query = """
        MERGE (y:ApprovalYear {year: $year})
        """
        with self.driver.session() as session:
            session.run(query, year=year)
    
    # -------------------------------------------------------------------------------------------- #

    def create_relationships(self, drug_id, indications, contraindications, route, approval_year):
        with self.driver.session() as session:
            for ind in indications:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (dis:Disease {id: $dis_id})
                MERGE (d)-[:TREATS]->(dis)
                """, {"drug_id": drug_id, "dis_id": ind["id"]})
            
            for con in contraindications:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (dis:Disease {id: $dis_id})
                MERGE (d)-[:CONTRAINDICATED_FOR]->(dis)
                """, {"drug_id": drug_id, "dis_id": con["id"]})
            
            if route:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (r:AdminRoute {name: $route})
                MERGE (d)-[:ADMINISTERED_VIA]->(r)
                """, {"drug_id": drug_id, "route": route})
            
            if approval_year:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (y:ApprovalYear {year: $year})
                MERGE (d)-[:APPROVED_IN]->(y)
                """, {"drug_id": drug_id, "year": approval_year})

    # -------------------------------------------------------------------------------------------- #

    def insert_data(self, drug, diseases, indications, contraindications):
        self.create_drug(drug)
        for disease in diseases:
            self.create_disease(disease)
        self.create_admin_route(drug.get("admin_route"))
        self.create_approval_year(drug.get("approval_year"))
        self.create_relationships(drug["id"], indications, contraindications, drug.get("admin_route"), drug.get("approval_year"))

    # -------------------------------------------------------------------------------------------- #

def load_json(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)
    
# -------------------------------------------------------------------------------------------- #

def clean_id(url):
    if not url or not isinstance(url, str):
        return None
    
    if url.startswith('http://purl.obolibrary.org/obo/'):
        return url.split('/')[-1]
    
    return url.split('/')[-1]

# -------------------------------------------------------------------------------------------- #

def extract_year(approval_date):
    if not approval_date:
        return None
    
    if isinstance(approval_date, int):
        return str(approval_date)[:4]
    
    if isinstance(approval_date, str):
        try:
            # Tenta primeiro com o mês abreviado (ex: Mar)
            parsed_date = datetime.strptime(approval_date, "%b %d, %Y")
            return str(parsed_date.year)
        except ValueError:
            try:
                # Tenta depois com o mês completo (ex: March)
                parsed_date = datetime.strptime(approval_date, "%B %d, %Y")
                return str(parsed_date.year)
            except ValueError:
                pass
        
        if approval_date.isdigit():
            if len(approval_date) == 8:
                return approval_date[:4]
            elif len(approval_date) == 4:
                return approval_date
    
    return None

# -------------------------------------------------------------------------------------------- #

def process_xml_file(file_path, neo4j_handler):
    try:
        data = load_json(file_path)
        
        for drug_entry in data.get("drug", []):
            drug_id = clean_id(drug_entry.get("chebi_id")) or clean_id(drug_entry.get("drugbank_id"))
            if not drug_id:
                continue 
            
            approval_date = (
                data.get("Approval_Date") or
                data.get("Approval Date") or 
                drug_entry.get("approval_date") or 
                data.get("effectiveTime") or 
                data.get("date")
            )
            
            approval_year = extract_year(approval_date)
            
            admin_route = drug_entry.get("admin_route") or data.get("Route of Administration")
            drug = {
                "id": drug_id,
                "name": drug_entry.get("name"),
                "organization": data.get("organization") or data.get("Applicant"),
                "effectiveTime": data.get("effectiveTime"),
                "admin_route": admin_route,
                "approval_year": approval_year
            }
            
            diseases = []
            indications = []
            contraindications = []
            
            for ind in data.get("indications", []):
                # Prioritize doid_id, fallback to orphanet_id
                doid_id = clean_id(ind.get("doid_id"))
                orphanet_id = clean_id(ind.get("orphanet_id"))
                disease_id = doid_id or orphanet_id  # Use doid_id if available, otherwise orphanet_id
                
                if disease_id:
                    diseases.append({"id": disease_id, "name": ind.get("text", "Unknown")})
                    indications.append({"id": disease_id})
            
            for con in data.get("contraindications", []):
                # Prioritize doid_id, fallback to orphanet_id
                doid_id = clean_id(con.get("doid_id"))
                orphanet_id = clean_id(con.get("orphanet_id"))
                disease_id = doid_id or orphanet_id  # Use doid_id if available, otherwise orphanet_id
                
                if disease_id:
                    diseases.append({"id": disease_id, "name": con.get("text", "Unknown")})
                    contraindications.append({"id": disease_id})
            
            print(f"Drug: {drug_id}, Admin Route: {admin_route}, Approval Year: {approval_year}")
            
            neo4j_handler.insert_data(drug, diseases, indications, contraindications)
    except Exception as e:
        print(f"Error processing file '{file_path}': {e}")