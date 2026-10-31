"""
Prepare a Purple Book monthly data file for conversion.

The FDA monthly file (purplebook-search-<month>-data-download.csv) contains two
tables, each starting with a header line "N/R/U,Applicant,BLA Number,...":

  1. the month's change report (newly approved, added and updated products);
  2. the full list of all products in the Purple Book that month.

It also contains rows made only of commas (empty rows). For the knowledge graph
only the full list is used. This module keeps the 3 title lines at the top (the
conversion skips exactly 3 lines: skiprows=3), then the header and rows of the
LAST table, without empty rows. A file already prepared is left unchanged.

    from jsonify.purple_book import prepare_purple_book_file
    prepare_purple_book_file('jsonify/input/csv_files/purplebook-search-may-data-download.csv')
"""

import os
import re

HEADER_START = 'N/R/U,'
TITLE_LINES = 3                       # matches skiprows=3 in conversion.py
_EMPTY_ROW = re.compile(r'^[,\s]*$')


def clean_purple_book_text(text):
    """
    Return (cleaned text, info). `info` says what was removed; the text is
    returned unchanged if it is not a Purple Book file (no "N/R/U," header).
    """
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if line.startswith(HEADER_START)]
    if not headers:
        return text, {'purple_book': False}

    last = headers[-1]
    title = lines[:TITLE_LINES]
    while len(title) < TITLE_LINES:                    # keep skiprows=3 valid
        title.append('')
    body = [lines[last]] + [l for l in lines[last + 1:] if not _EMPTY_ROW.match(l)]

    info = {
        'purple_book': True,
        'tables': len(headers),
        'change_report_rows_removed': (last - headers[0] - 1) if len(headers) > 1 else 0,
        'empty_rows_removed': sum(1 for l in lines[last + 1:] if _EMPTY_ROW.match(l)),
        'product_rows': len(body) - 1,
    }
    cleaned = '\n'.join(title + body) + '\n'
    return cleaned, info


def prepare_purple_book_file(path, keep_original=True):
    """
    Clean a Purple Book CSV in place (UTF-8). The original is kept once as
    <name>.original.txt (not .csv, so the conversion does not read it).
    Returns the info dict of clean_purple_book_text.
    """
    raw = open(path, 'rb').read()
    try:
        text = raw.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = raw.decode('latin-1')
    cleaned, info = clean_purple_book_text(text)
    if info.get('purple_book') and cleaned.splitlines() != text.splitlines():
        if keep_original:
            original = os.path.splitext(path)[0] + '.original.txt'
            if not os.path.exists(original):
                with open(original, 'wb') as f:
                    f.write(raw)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(cleaned)
        print(f"INFO: Purple Book file prepared: kept the full product list "
              f"({info['product_rows']} rows); removed the change report "
              f"({info['change_report_rows_removed']} rows) and "
              f"{info['empty_rows_removed']} empty rows")
    return info