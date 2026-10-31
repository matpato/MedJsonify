"""
List the Python packages imported by the MedJsonify code that are missing in
this environment (run inside the standalone image by run_medjsonify.sh --check).

The Airflow image installs many packages as Airflow's own dependencies
(requests, tenacity, PyYAML, ...). Code can rely on them without them being
in requirements.txt; the light standalone image then lacks them. This scans
every .py file once and reports them all, with the pip name to add to
standalone/requirements-extra.txt.

    python3 check_imports.py [folder ...]      (default: /opt/airflow/dags)
"""

import ast
import importlib.util
import os
import sys
from collections import defaultdict

SKIP_DIRS = {'__pycache__', '.git', 'logs', 'input', 'output', 'downloads',
             'preprocessing', 'entities', 'node_modules', '.venv', 'venv'}

# import name -> pip package name, where they differ
PIP_NAMES = {
    'bs4': 'beautifulsoup4', 'yaml': 'PyYAML', 'dateutil': 'python-dateutil',
    'sklearn': 'scikit-learn', 'PIL': 'Pillow', 'cv2': 'opencv-python',
    'dotenv': 'python-dotenv', 'Bio': 'biopython', 'owlready2': 'Owlready2',
    'pronto': 'pronto', 'rdflib': 'rdflib', 'neo4j': 'neo4j', 'py2neo': 'py2neo',
    'psycopg2': 'psycopg2-binary', 'jose': 'python-jose', 'magic': 'python-magic',
    'docx': 'python-docx', 'Levenshtein': 'python-Levenshtein', 'fitz': 'PyMuPDF',
}


def local_names(roots):
    """Top-level modules and packages that are part of the project itself."""
    names = set()
    for root in roots:
        for path in [root] + [os.path.join(root, d) for d in os.listdir(root)
                              if os.path.isdir(os.path.join(root, d))]:
            try:
                entries = os.listdir(path)
            except OSError:
                continue
            for entry in entries:
                if entry.endswith('.py'):
                    names.add(entry[:-3])
                elif os.path.isdir(os.path.join(path, entry)):
                    names.add(entry)
    return names


def imports_in(path):
    """(module, line, optional) for each absolute import in a file."""
    try:
        tree = ast.parse(open(path, encoding='utf-8', errors='replace').read())
    except SyntaxError:
        return []
    optional_lines = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            handled = {getattr(h.type, 'id', None) for h in node.handlers}
            handled |= {getattr(e, 'id', None) for h in node.handlers
                        if isinstance(h.type, ast.Tuple) for e in h.type.elts}
            if handled & {'ImportError', 'ModuleNotFoundError', 'Exception', None}:
                for inner in node.body:
                    for sub in ast.walk(inner):
                        if hasattr(sub, 'lineno'):
                            optional_lines.add(sub.lineno)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name.split('.')[0], node.lineno, node.lineno in optional_lines))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.append((node.module.split('.')[0], node.lineno, node.lineno in optional_lines))
    return found


def main():
    roots = sys.argv[1:] or ['/opt/airflow/dags']
    roots = [os.path.realpath(r) for r in roots if os.path.isdir(r)]
    project = local_names(roots) | {'airflow'}   # airflow: handled by run_task.py

    missing = defaultdict(list)
    files = 0
    for root in roots:
        for dirpath, dirnames, filenames in os.walk(root, followlinks=True):
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith('.')]
            for name in filenames:
                if not name.endswith('.py'):
                    continue
                files += 1
                path = os.path.join(dirpath, name)
                for module, line, optional in imports_in(path):
                    if module in project or module == '__future__':
                        continue
                    if importlib.util.find_spec(module) is None:
                        missing[module].append((os.path.relpath(path, root), line, optional))

    print(f"Scanned {files} Python files under: {', '.join(roots)}")
    required = {m: w for m, w in missing.items() if not all(opt for _, _, opt in w)}
    optional = {m: w for m, w in missing.items() if m not in required}

    if not missing:
        print("All imported packages are installed.")
        return 0

    if required:
        print(f"\nMISSING ({len(required)}): add these lines to standalone/requirements-extra.txt")
        print("then run with --rebuild:\n")
        for module in sorted(required):
            print(f"    {PIP_NAMES.get(module, module)}")
        print("\nWhere they are imported:")
        for module in sorted(required):
            for path, line, _ in required[module][:3]:
                print(f"  {module:<20} {path}:{line}")
            if len(required[module]) > 3:
                print(f"  {'':<20} ... and {len(required[module]) - 3} more")
    if optional:
        print(f"\nOptional (imported inside try/except, the code works without them):")
        for module in sorted(optional):
            path, line, _ = optional[module][0]
            print(f"  {module:<20} {path}:{line}")
    return 1 if required else 0


if __name__ == '__main__':
    sys.exit(main())