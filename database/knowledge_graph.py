###############################################################################
#                                                                             #  
# @file: knowledge_graph.py                                                   #  
# @description: Neo4j knowledge graph creation for pharmaceutical data        #
# @date: May 2025                                                             #
# @version: 2.0                                                               #  
#                                                                             #  
# This module handles the creation of a pharmaceutical knowledge graph in     #
# Neo4j. It processes JSON data containing drug and disease information,      #
# normalizes identifiers, and creates nodes and relationships in the graph    #
# database. The resulting knowledge graph represents drugs, diseases, and     #
# their relationships such as indications and contraindications.              #
#                                                                             #  
###############################################################################

import json
import os
from neo4j import GraphDatabase
from datetime import datetime

class Neo4jHandler:
    """
    Handles interactions with the Neo4j graph database.
    
    This class provides methods to create and manage a pharmaceutical knowledge graph,
    including creating nodes for drugs, diseases, administration routes, and approval years,
    as well as establishing relationships between them.
    
    Attributes:
        driver: Neo4j database driver for connecting to the database
    """
    def __init__(self, uri, user, password):
        """
        Initialize the Neo4j handler with connection parameters.
        
        Args:
            uri (str): URI of the Neo4j database
            user (str): Username for authentication
            password (str): Password for authentication
        """
        # OBJECTIVE: Establish connection to Neo4j database
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        """
        Close the Neo4j database connection.
        """
        # OBJECTIVE: Clean up resources by closing the database connection
        self.driver.close()
    
    def create_constraints(self):
        """
        Create uniqueness constraints for node properties in the Neo4j database.
        
        This ensures that key properties like drug IDs, disease IDs, etc. are unique
        in the database, which improves query performance and maintains data integrity.
        """
        # OBJECTIVE: Set up database constraints to ensure data integrity
        with self.driver.session() as session:
            # Ensure Drug nodes have unique IDs
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (d:Drug) ASSERT d.id IS UNIQUE")
            # Ensure Disease nodes have unique IDs
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (disease:Disease) ASSERT disease.id IS UNIQUE")
            # Ensure AdminRoute nodes have unique names
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (r:AdminRoute) ASSERT r.name IS UNIQUE")
            # Ensure ApprovalYear nodes have unique years
            session.run("CREATE CONSTRAINT IF NOT EXISTS ON (y:ApprovalYear) ASSERT y.year IS UNIQUE") 

    
    def create_drug(self, drug):
        """
        Create or update a Drug node in the knowledge graph.
        
        Args:
            drug (dict): Dictionary containing drug information
                         (id, name, organization, effectiveTime)
        """
        # OBJECTIVE: Create or update Drug nodes with properties
        query = """
        MERGE (d:Drug {id: $id})
        SET d.name = $name, d.organization = $organization, d.effectiveTime = $effectiveTime
        """
        with self.driver.session() as session:
            session.run(query, **drug)

    
    def create_disease(self, disease):
        """
        Create or update a Disease node in the knowledge graph.
        
        Args:
            disease (dict): Dictionary containing disease information
                           (id, name)
        """
        # OBJECTIVE: Create or update Disease nodes with properties
        query = """
        MERGE (d:Disease {id: $id})
        SET d.name = $name
        """
        with self.driver.session() as session:
            session.run(query, **disease)

    def create_admin_route(self, route):
        """
        Create Administration Route nodes in the knowledge graph.
        
        The route string may contain multiple administration routes separated by commas.
        Each route will be created as a separate node.
        
        Args:
            route (str): Administration route(s) as a string, comma-separated if multiple
        """
        # OBJECTIVE: Create AdminRoute nodes for each administration route
        if not route:
            return
            
        # Split multiple routes if separated by commas and strip whitespace
        routes = [r.strip() for r in route.split(",")] 
        
        with self.driver.session() as session:
            for r in routes:
                query = """
                MERGE (r:AdminRoute {name: $route})
                """
                session.run(query, route=r)
    
    def create_approval_year(self, year):
        """
        Create an Approval Year node in the knowledge graph.
        
        Args:
            year (str): The year of drug approval
        """
        # OBJECTIVE: Create ApprovalYear node if a year is provided
        if not year:
            return
            
        query = """
        MERGE (y:ApprovalYear {year: $year})
        """
        with self.driver.session() as session:
            session.run(query, year=year)

    def create_relationships(self, drug_id, indications, contraindications, route, approval_year):
        """
        Create relationships between nodes in the knowledge graph.
        
        This method creates various relationships:
        - TREATS: between Drug and Disease (for indications)
        - CONTRAINDICATED_FOR: between Drug and Disease (for contraindications)
        - ADMINISTERED_VIA: between Drug and AdminRoute
        - APPROVED_IN: between Drug and ApprovalYear
        
        Args:
            drug_id (str): The ID of the drug node
            indications (list): List of diseases that the drug treats
            contraindications (list): List of diseases for which the drug is contraindicated
            route (str): Administration route(s) for the drug
            approval_year (str): Year the drug was approved
        """
        # OBJECTIVE: Establish relationships between nodes in the knowledge graph
        with self.driver.session() as session:
            # Create TREATS relationships between Drug and indicated Diseases
            for ind in indications:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (dis:Disease {id: $dis_id})
                MERGE (d)-[:TREATS]->(dis)
                """, {"drug_id": drug_id, "dis_id": ind["id"]})
            
            # Create CONTRAINDICATED_FOR relationships between Drug and contraindicated Diseases
            for con in contraindications:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (dis:Disease {id: $dis_id})
                MERGE (d)-[:CONTRAINDICATED_FOR]->(dis)
                """, {"drug_id": drug_id, "dis_id": con["id"]})
            
            # Create ADMINISTERED_VIA relationship between Drug and AdminRoute
            if route:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (r:AdminRoute {name: $route})
                MERGE (d)-[:ADMINISTERED_VIA]->(r)
                """, {"drug_id": drug_id, "route": route})
            
            # Create APPROVED_IN relationship between Drug and ApprovalYear
            if approval_year:
                session.run("""
                MATCH (d:Drug {id: $drug_id}), (y:ApprovalYear {year: $year})
                MERGE (d)-[:APPROVED_IN]->(y)
                """, {"drug_id": drug_id, "year": approval_year})

                
    def insert_data(self, drug, diseases, indications, contraindications):
        """
        Insert all data for a drug into the knowledge graph.
        
        This method orchestrates the creation of all nodes and relationships
        for a single drug entry.
        
        Args:
            drug (dict): Drug information
            diseases (list): List of disease information
            indications (list): List of diseases indicated for the drug
            contraindications (list): List of diseases contraindicated for the drug
        """
        # OBJECTIVE: Orchestrate the complete insertion of drug-related data
        # Create or update the Drug node
        self.create_drug(drug)
        
        # Create or update all Disease nodes
        for disease in diseases:
            self.create_disease(disease)
            
        # Create AdminRoute node(s) if provided
        self.create_admin_route(drug.get("admin_route"))
        
        # Create ApprovalYear node if provided
        self.create_approval_year(drug.get("approval_year"))
        
        # Create all relationships between nodes
        self.create_relationships(drug["id"], indications, contraindications, 
                                drug.get("admin_route"), drug.get("approval_year"))

# -------------------------------------------------------------------------------------------- #
# UTILITY FUNCTIONS FOR PROCESSING DATA
# -------------------------------------------------------------------------------------------- #

def load_json(file_path):
    """
    Load JSON data from a file.
    
    Args:
        file_path (str): Path to the JSON file
        
    Returns:
        dict: Parsed JSON data
    """
    # OBJECTIVE: Load and parse JSON data from file
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)

def clean_id(url):
    """
    Extract a clean identifier from a URL or ID string.
    
    This function handles different ID formats, particularly extracting the
    final component from ontology URLs.
    
    Args:
        url (str): URL or ID string to clean
        
    Returns:
        str or None: Cleaned ID or None if input is invalid
    """
    # OBJECTIVE: Normalize identifiers by cleaning URLs and other ID formats
    if not url or not isinstance(url, str):
        return None
    
    # Handle ontology URLs by extracting the ID portion
    if url.startswith('http://purl.obolibrary.org/obo/'):
        return url.split('/')[-1]
    
    # For other URLs, take the last segment as the ID
    return url.split('/')[-1]
def extract_year(approval_date):
    """
    Extract the year from various date formats.
    
    This function attempts to extract a 4-digit year from different date formats,
    including:
    - Month abbreviation format (e.g., "Mar 15, 2022")
    - Full month name format (e.g., "March 15, 2022")
    - Numeric date strings (e.g., "20220315" or "2022")
    - Integer values that include a year
    
    Args:
        approval_date: Date in various possible formats
        
    Returns:
        str or None: The 4-digit year as a string, or None if extraction fails
    """
    # OBJECTIVE: Extract a standardized year from various date formats
    if not approval_date:
        return None
    
    # Handle integer dates (e.g., year or possibly YYYYMMDD)
    if isinstance(approval_date, int):
        return str(approval_date)[:4]  # Take first 4 digits as year
    
    if isinstance(approval_date, str):
        try:
            # Try with abbreviated month format (e.g., "Mar 15, 2022")
            parsed_date = datetime.strptime(approval_date, "%b %d, %Y")
            return str(parsed_date.year)
        except ValueError:
            try:
                # Try with full month name format (e.g., "March 15, 2022")
                parsed_date = datetime.strptime(approval_date, "%B %d, %Y")
                return str(parsed_date.year)
            except ValueError:
                pass
        
        # Handle numeric strings that might contain a year
        if approval_date.isdigit():
            if len(approval_date) == 8:  # Likely YYYYMMDD format
                return approval_date[:4]
            elif len(approval_date) == 4:  # Likely YYYY format
                return approval_date
    
    return None
def process_xml_file(file_path, neo4j_handler):
    """
    Process a JSON file (derived from XML) and load data into Neo4j.
    
    This function extracts drug and disease information from a JSON file,
    transforms it into the required format, and loads it into the Neo4j database.
    
    Args:
        file_path (str): Path to the JSON file
        neo4j_handler (Neo4jHandler): Handler for Neo4j database operations
    """
    # OBJECTIVE: Process a JSON file and import its data into the Neo4j graph
    try:
        # Load the JSON data from file
        data = load_json(file_path)
        
        # OBJECTIVE: Process each drug entry in the data
        for drug_entry in data.get("drug", []):
            # Extract and clean drug ID, prioritizing chebi_id over drugbank_id
            drug_id = clean_id(drug_entry.get("chebi_id")) or clean_id(drug_entry.get("drugbank_id"))
            if not drug_id:
                continue  # Skip drugs without a valid ID
            
            # OBJECTIVE: Extract and standardize approval date information
            # Try multiple possible field names for approval date
            approval_date = (
                data.get("Approval_Date") or
                data.get("Approval Date") or 
                drug_entry.get("approval_date") or 
                data.get("effectiveTime") or 
                data.get("date")
            )
            
            # Convert approval date to a standardized year format
            approval_year = extract_year(approval_date)
            
            # Extract administration route information
            admin_route = drug_entry.get("admin_route") or data.get("Route of Administration")
            
            # OBJECTIVE: Prepare drug data for the knowledge graph
            drug = {
                "id": drug_id,
                "name": drug_entry.get("name"),
                "organization": data.get("organization") or data.get("Applicant"),
                "effectiveTime": data.get("effectiveTime"),
                "admin_route": admin_route,
                "approval_year": approval_year
            }
            
            # Initialize lists for disease data
            diseases = []
            indications = []
            contraindications = []
            
            # OBJECTIVE: Extract and process indications (diseases the drug treats)
            for ind in data.get("indications", []):
                # Prioritize doid_id, fallback to orphanet_id
                doid_id = clean_id(ind.get("doid_id"))
                orphanet_id = clean_id(ind.get("orphanet_id"))
                disease_id = doid_id or orphanet_id  # Use doid_id if available, otherwise orphanet_id
                
                if disease_id:
                    # Add to list of diseases
                    diseases.append({"id": disease_id, "name": ind.get("text", "Unknown")})
                    # Add to list of indications for this drug
                    indications.append({"id": disease_id})
            
            # OBJECTIVE: Extract and process contraindications (diseases the drug should not be used for)
            for con in data.get("contraindications", []):
                # Prioritize doid_id, fallback to orphanet_id
                doid_id = clean_id(con.get("doid_id"))
                orphanet_id = clean_id(con.get("orphanet_id"))
                disease_id = doid_id or orphanet_id  # Use doid_id if available, otherwise orphanet_id
                
                if disease_id:
                    # Add to list of diseases
                    diseases.append({"id": disease_id, "name": con.get("text", "Unknown")})
                    # Add to list of contraindications for this drug
                    contraindications.append({"id": disease_id})
            
            # Log summary of the drug being processed
            print(f"Drug: {drug_id}, Admin Route: {admin_route}, Approval Year: {approval_year}")
            
            # OBJECTIVE: Insert all extracted data into the Neo4j knowledge graph
            neo4j_handler.insert_data(drug, diseases, indications, contraindications)
    except Exception as e:
        # Log any errors that occur during processing
        print(f"Error processing file '{file_path}': {e}")