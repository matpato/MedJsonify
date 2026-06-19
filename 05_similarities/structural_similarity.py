###############################################################################
#                                                                             #
# @file: structural_similarity.py                                             #
# @description: Calculate structural similarity between drugs (CHEBI IDs)     #
# @date: June 2026                                                            #
# @version: 1.0                                                               #
#                                                                             #
# (author: Matilde Pato & Carolina Pereira)                                   #
#                                                                             #
# Reads CHEBI IDs from indicated.csv and contraindicated.csv, computes        #
# pairwise Tanimoto + Morgan structural similarity via RDKit/ChEBI SMILES,    #
# filters pairs where |tanimoto| < 0.7, and writes similar.csv.               #
#                                                                             #
###############################################################################

import itertools
import logging
import os
import requests
from pathlib import Path

import pandas as pd
from rdkit import Chem, DataStructs
from rdkit.Chem import rdMolDescriptors

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# ---------------------------------------------------------------------------- #
# Constants
# ---------------------------------------------------------------------------- #

SIMILARITY_THRESHOLD = 0.7   # |tanimoto| < threshold → include in similar.csv
CHEBI_PREFIX = "CHEBI_"


# ---------------------------------------------------------------------------- #
# RDKit helpers  (adapted from KB)
# ---------------------------------------------------------------------------- #

class _MyFloat:
    """Workaround for rdkit returning floats that don't support subscript."""
    def __init__(self, f):
        self.f = f
    def __getitem__(self, index):
        return self.f


def _mol_from_smiles(smile: str):
    try:
        mol = Chem.MolFromSmiles(smile, sanitize=False)
        mol.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(
            mol,
            Chem.SanitizeFlags.SANITIZE_FINDRADICALS |
            Chem.SanitizeFlags.SANITIZE_KEKULIZE |
            Chem.SanitizeFlags.SANITIZE_SETAROMATICITY |
            Chem.SanitizeFlags.SANITIZE_SETCONJUGATION |
            Chem.SanitizeFlags.SANITIZE_SETHYBRIDIZATION |
            Chem.SanitizeFlags.SANITIZE_SYMMRINGS,
            catchErrors=True,
        )
        return mol
    except Exception as e:
        logging.debug(f"Molecule error: {e}")
        return None


def _structural_similarity(smile1: str, smile2: str) -> dict:
    """
    Compute Tanimoto (RDKit fingerprint) and Morgan (Dice) similarity
    between two SMILES strings.

    Returns dict with keys 'tanimoto' and 'morgan' (both 0.0 on failure).
    """
    result = {'tanimoto': 0.0, 'morgan': 0.0}
    try:
        mol1 = _mol_from_smiles(smile1)
        mol2 = _mol_from_smiles(smile2)
        if mol1 is None or mol2 is None:
            return result

        # Tanimoto
        fp1 = Chem.RDKFingerprint(mol1)
        fp2 = Chem.RDKFingerprint(mol2)
        result['tanimoto'] = _MyFloat(round(DataStructs.TanimotoSimilarity(fp1, fp2), 7))[0]

        # Morgan / Dice
        mfp1 = rdMolDescriptors.GetMorganFingerprint(mol1, 2)
        mfp2 = rdMolDescriptors.GetMorganFingerprint(mol2, 2)
        result['morgan'] = _MyFloat(round(DataStructs.DiceSimilarity(mfp1, mfp2), 7))[0]

    except Exception as e:
        logging.debug(f"Similarity error: {e}")

    return result


# ---------------------------------------------------------------------------- #
# ChEBI SMILES fetcher  (adapted from KB)
# ---------------------------------------------------------------------------- #

def _fetch_smiles(chebi_ids: list) -> pd.DataFrame:
    """
    Fetch SMILES for a list of CHEBI IDs (e.g. 'CHEBI_12345') via ChEBI 2.0 REST API.
    Returns a DataFrame with columns ['chebi', 'smile'].
    """
    # ChEBI 2.0 REST API (SOAP was retired in Sep 2025)
    # endpoint: /chebi/backend/api/public/compound/{numeric_id}/
    CHEBI_API = "https://www.ebi.ac.uk/chebi/backend/api/public/compound"

    smile_rows = []

    for chebi_id in chebi_ids:
        numeric_id = chebi_id.replace('CHEBI_', '').replace('CHEBI:', '')
        try:
            resp = requests.get(
                f"{CHEBI_API}/{numeric_id}/",
                headers={'Accept': 'application/json'},
                timeout=15
            )
            if resp.ok:
                data = resp.json()
                # SMILES is under default_structure.smiles
                struct = data.get('default_structure', {})
                smiles = struct.get('smiles') if isinstance(struct, dict) else None
                if smiles:
                    smile_rows.append({'chebi': chebi_id, 'smile': smiles})
                    logging.info(f"  Got SMILES for {chebi_id}")
                else:
                    logging.debug(f"  No SMILES for {chebi_id}: keys={list(data.keys())}")
            else:
                logging.warning(f"  HTTP {resp.status_code} for {chebi_id}: {resp.text[:100]}")
        except Exception as e:
            logging.warning(f"  Error fetching {chebi_id}: {e}")

    return pd.DataFrame(smile_rows, columns=['chebi', 'smile'])


# ---------------------------------------------------------------------------- #
# Core logic
# ---------------------------------------------------------------------------- #

def _extract_chebi_ids(csv_path: str) -> list:
    """
    Read a CSV with a 'drugs' column and return unique CHEBI IDs
    (rows where the drug ID starts with CHEBI_).
    """
    df = pd.read_csv(csv_path)
    if 'drugs' not in df.columns:
        raise ValueError(f"'drugs' column not found in {csv_path}")
    chebi_ids = df['drugs'][df['drugs'].str.startswith(CHEBI_PREFIX)].unique().tolist()
    return chebi_ids


def compute_similar_csv(
    indicated_csv: str,
    contraindicated_csv: str,
    output_path: str,
    threshold: float = SIMILARITY_THRESHOLD,
) -> pd.DataFrame:
    """
    Compute pairwise structural similarity between all CHEBI drugs found in
    indicated.csv and contraindicated.csv, filter by threshold, and write
    similar.csv.

    Args:
        indicated_csv:      Path to indicated.csv
        contraindicated_csv: Path to contraindicated.csv
        output_path:        Path to write similar.csv
        threshold:          Keep pairs where tanimoto < threshold (default 0.7)

    Returns:
        DataFrame with columns [drugsA, drugsB, tanimoto, morgan]
    """
    # 1. Collect unique CHEBI IDs from both CSVs
    logging.info("Reading drug IDs from CSVs...")
    chebi_indicated     = _extract_chebi_ids(indicated_csv)
    chebi_contraindicated = _extract_chebi_ids(contraindicated_csv)
    chebi_all = list(set(chebi_indicated + chebi_contraindicated))
    logging.info(f"Found {len(chebi_all)} unique CHEBI drugs")

    if len(chebi_all) < 2:
        logging.warning("Not enough CHEBI drugs to compute similarity.")
        return pd.DataFrame(columns=['drugsA', 'drugsB', 'tanimoto', 'morgan'])

    # 2. Fetch SMILES from ChEBI
    logging.info("Fetching SMILES from ChEBI web service (this may take a while)...")
    smiles_df = _fetch_smiles(chebi_all)
    logging.info(f"Got SMILES for {len(smiles_df)} / {len(chebi_all)} drugs")

    if smiles_df.empty:
        logging.error("No SMILES retrieved — cannot compute similarity.")
        return pd.DataFrame(columns=['drugsA', 'drugsB', 'tanimoto', 'morgan'])

    smiles_map = smiles_df.set_index('chebi')['smile'].to_dict()
    valid_ids  = list(smiles_map.keys())

    # 3. Compute pairwise similarity for all combinations
    logging.info(f"Computing pairwise similarity for {len(valid_ids)} drugs...")
    rows = []
    pairs = list(itertools.combinations(valid_ids, 2))
    total = len(pairs)

    for i, (drugA, drugB) in enumerate(pairs):
        if i % 100 == 0:
            logging.info(f"  {i}/{total} pairs processed...")

        sim = _structural_similarity(smiles_map[drugA], smiles_map[drugB])

        # Filter: keep pairs where tanimoto < threshold
        if sim['tanimoto'] > 0 and sim['tanimoto'] < threshold:
            rows.append({
                'drugsA':    drugA,
                'drugsB':    drugB,
                'tanimoto':  sim['tanimoto'],
                'morgan':    sim['morgan'],
            })

    result_df = pd.DataFrame(rows, columns=['drugsA', 'drugsB', 'tanimoto', 'morgan'])
    logging.info(f"Found {len(result_df)} similar pairs (tanimoto < {threshold})")

    # 4. Write output
    os.makedirs(Path(output_path).parent, exist_ok=True)
    result_df.to_csv(output_path, index=False)
    logging.info(f"Saved similar.csv -> {output_path}")

    return result_df


# ---------------------------------------------------------------------------- #
# Standalone usage
# ---------------------------------------------------------------------------- #

if __name__ == '__main__':
    BASE = Path(__file__).parent.parent / '04_database' / 'output'

    result = compute_similar_csv(
        indicated_csv=str(BASE / 'indicated.csv'),
        contraindicated_csv=str(BASE / 'contraindicated.csv'),
        output_path=str(BASE / 'similar.csv'),
    )
    print(f"\nDone: {len(result)} pairs written to similar.csv")
