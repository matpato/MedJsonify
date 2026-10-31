"""
Approval years for DailyMed products, from the Orange Book and the Purple Book.

A DailyMed label (SPL) has no approval date, but it has the number of the FDA
application it was approved under (e.g. NDA020702, ANDA075123, BLA761299).
The Orange Book (NDA/ANDA) and the Purple Book (BLA) list each application
with its approval date, so the application number links the three sources.

    year, source = approval_year('NDA020702', marketing_start='20030115')
    # -> (2003, 'orange_book')

`source` says where the year came from, so it can be reported:
    'orange_book' / 'purple_book'  approval year of the application
    'orange_book_prior_1982'       approved before 1982, no exact date
                                   (year = PRIOR_1982_YEAR, None by default)
    'marketing_start'              first marketing date of the product
                                   (fallback; NOT an approval date)
    None                           no year found

The raw source files are read (not the converted JSON), because jsonifyer
keeps one record per ingredient / proper name and drops most applications.
Paths can be set with the environment variables ORANGE_BOOK_PRODUCTS and
PURPLE_BOOK_DIR; the defaults are the jsonify input folders.
"""

import csv
import datetime
import glob
import io
import os
import re
import threading
from typing import Dict, Optional, Tuple

ORANGE_BOOK_PRODUCTS = os.environ.get(
    'ORANGE_BOOK_PRODUCTS', '/opt/airflow/dags/jsonify/input/txt_files/products.txt')
PURPLE_BOOK_DIR = os.environ.get(
    'PURPLE_BOOK_DIR', '/opt/airflow/dags/jsonify/input/csv_files')

# Use the product's first marketing date when no application matches
# (e.g. OTC monograph products, which have no NDA/ANDA/BLA)
USE_MARKETING_START_FALLBACK = True

# Orange Book products approved before 1982 have no date, only the text
# "Approved Prior to Jan 1, 1982". None leaves them without a year;
# set to 1982 to use that year instead.
PRIOR_1982_YEAR = None

_APPL_RE = re.compile(r'^\s*(NDA|ANDA|BLA)\s*0*(\d+)\s*$', re.IGNORECASE)
_YEAR_RE = re.compile(r'\b(1[89]\d\d|20\d\d)\b')

_lock = threading.Lock()
_table = None          # (application key -> (year, source))
stats = {'orange_book': 0, 'purple_book': 0, 'prior_1982': 0}  # applications / rows


def application_key(approval_id) -> Optional[Tuple[str, int]]:
    """'NDA020702' -> ('NDA', 20702); None if not an NDA/ANDA/BLA number."""
    if not approval_id:
        return None
    if isinstance(approval_id, list):          # several products in one label
        approval_id = approval_id[0]
    m = _APPL_RE.match(str(approval_id))
    return (m.group(1).upper(), int(m.group(2))) if m else None


# Two-digit years, as in the Purple Book ("3-Nov-03", "11/03/03")
_SHORT_YEAR_RE = re.compile(r'^\s*\d{1,2}[-/ ](?:[A-Za-z]{3,9}|\d{1,2})[-/ ](\d{2})\s*$')


def parse_year(text) -> Optional[int]:
    """Year from '2003', 'Mar 26, 2003', '20030326', '3-Nov-03' or '11/03/03'."""
    if not text:
        return None
    text = str(text).strip()
    if text.isdigit() and len(text) == 8:          # 20250228
        text = text[:4]
    m = _YEAR_RE.search(text)
    if m:
        return int(m.group(1))
    m = _SHORT_YEAR_RE.match(text)
    if m:
        yy = int(m.group(1))
        # 00..(this year) -> 2000s, later -> 1900s (e.g. 03 -> 2003, 46 -> 1946)
        return 2000 + yy if yy <= datetime.date.today().year % 100 else 1900 + yy
    return None


def _keep_earliest(table, key, year, source):
    old = table.get(key)
    if year is None:
        return
    if old is None or old[0] is None or year < old[0]:
        table[key] = (year, source)


def _keep_prior_1982(table, key):
    """Application approved before 1982: no exact date, but known to be old.
    Recorded so that it does not fall back to a (much later) marketing date."""
    stats['prior_1982'] += 1
    old = table.get(key)
    if old is None or old[0] is None or old[1] != 'orange_book_prior_1982':
        table[key] = (PRIOR_1982_YEAR, 'orange_book_prior_1982')


def _read_text(path):
    raw = open(path, 'rb').read()
    try:
        return raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        return raw.decode('latin-1')


def _load_orange_book(table, path):
    if not os.path.exists(path):
        print(f"WARNING: Orange Book products file not found: {path}")
        return
    reader = csv.DictReader(io.StringIO(_read_text(path)), delimiter='~')
    for row in reader:
        appl_type = {'N': 'NDA', 'A': 'ANDA'}.get((row.get('Appl_Type') or '').strip().upper())
        number = (row.get('Appl_No') or '').strip()
        if appl_type and number.isdigit():
            key = (appl_type, int(number))
            date = row.get('Approval_Date') or ''
            if 'prior to' in date.lower():
                _keep_prior_1982(table, key)
            else:
                _keep_earliest(table, key, parse_year(date), 'orange_book')
    stats['orange_book'] = sum(1 for v in table.values() if v[1].startswith('orange_book'))


def _find_header(lines):
    """Index of the Purple Book header line (the file starts with title lines)."""
    for i, line in enumerate(lines[:20]):
        low = line.lower()
        if 'bla' in low and 'approval' in low:
            return i
    return None


def _load_purple_book(table, folder):
    files = sorted(glob.glob(os.path.join(folder, '*.csv')))
    if not files:
        print(f"WARNING: no Purple Book CSV found in {folder}")
        return
    for path in files:
        lines = _read_text(path).splitlines()
        header = _find_header(lines)
        if header is None:
            print(f"WARNING: no BLA/approval-date columns found in {os.path.basename(path)}")
            continue
        reader = csv.DictReader(lines[header:])
        cols = {c.lower().strip(): c for c in (reader.fieldnames or []) if c}
        bla_col = next((cols[c] for c in cols if 'bla' in c and ('number' in c or c.endswith('no'))), None)
        date_col = next((cols[c] for c in cols if 'approval date' in c), None)
        if not bla_col or not date_col:
            print(f"WARNING: BLA number / approval date columns not found in {os.path.basename(path)}")
            continue
        for row in reader:
            number = re.sub(r'\D', '', row.get(bla_col) or '')
            if number:
                _keep_earliest(table, ('BLA', int(number)), parse_year(row.get(date_col)), 'purple_book')
    stats['purple_book'] = sum(1 for v in table.values() if v[1] == 'purple_book')


def load(orange_book_products=ORANGE_BOOK_PRODUCTS, purple_book_dir=PURPLE_BOOK_DIR) -> Dict:
    """Build the application -> approval year table (once; later calls reuse it)."""
    global _table
    with _lock:
        if _table is None:
            stats.update(orange_book=0, purple_book=0, prior_1982=0)
            table = {}
            _load_orange_book(table, orange_book_products)
            _load_purple_book(table, purple_book_dir)
            _table = table
            print(f"Approval years loaded: {stats['orange_book']} Orange Book applications, "
                  f"{stats['purple_book']} Purple Book BLAs "
                  f"({stats['prior_1982']} Orange Book entries 'Approved Prior to Jan 1, 1982')")
    return _table


def approval_year(approval_id, marketing_start=None) -> Tuple[Optional[int], Optional[str]]:
    """(year, source) for a DailyMed product; see the module docstring."""
    key = application_key(approval_id)
    if key is not None:
        hit = load().get(key)
        if hit:
            return hit      # may be (None, 'orange_book_prior_1982')
    if USE_MARKETING_START_FALLBACK and marketing_start:
        if isinstance(marketing_start, list):
            marketing_start = min(str(m) for m in marketing_start)
        year = parse_year(marketing_start)
        if year:
            return year, 'marketing_start'
    return None, None