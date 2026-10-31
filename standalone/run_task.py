"""
Run one MedJsonify Airflow task outside Airflow.

The task functions are the ones defined in your DAG file(s); nothing is
copied or rewritten, so Airflow and standalone mode run exactly the same code.

    python3 run_task.py --list                          # tasks found in the DAG files
    python3 run_task.py convert_files_to_json_task      # run one task
    python3 run_task.py ner_process_task --ds 2025-05-01
    python3 run_task.py download_vocabulary_task --param vocabulary_name=drugbank

How the task is found: every .py file in the DAGs folder (and its subfolders)
is scanned without being executed, and the file that defines a module-level
function with that name is imported and the function is called. The DAGs
folder is put on sys.path first, as Airflow does, so imports such as
`from jsonify.conversion import ...` work unchanged.

Airflow context: the call receives ds, ds_nodash, logical_date, params and
ti=None. A task that reads XCom through `ti` cannot run outside Airflow; the
error then says so.

Airflow does not need to be installed. If it is missing, an empty stand-in is
used so that the DAG file can be imported (`from airflow import DAG`, the
operators, `with DAG(...)`, `t1 >> t2`, @task/@dag, Variable.get(..., default_var=...)).
Only the task functions themselves are run, so none of it is needed.
"""

import argparse
import ast
import datetime
import importlib.util
import inspect
import logging
import os
import sys
import time
import traceback
from pathlib import Path

DEFAULT_DAGS_DIR = os.environ.get('AIRFLOW_DAGS_DIR', '/opt/airflow/dags')


# ---------------------------------------------------------------------------
# Stand-in for Airflow, used only when Airflow is not installed
# ---------------------------------------------------------------------------
class _AirflowStub:
    """Accepts any use the DAG file makes of Airflow objects, and does nothing."""

    def __init__(self, *args, **kwargs):
        pass

    def __call__(self, *args, **kwargs):
        # Decorators: @task / @dag / @task(...) leave the function as it is
        if len(args) == 1 and callable(args[0]) and not kwargs and not isinstance(args[0], _AirflowStub):
            return args[0]
        # Variable.get('x', default_var=...) returns the default
        if 'default_var' in kwargs:
            return kwargs['default_var']
        return _AirflowStub()

    def __getattr__(self, name):
        if name.startswith('__') and name.endswith('__'):
            raise AttributeError(name)
        return _AirflowStub()

    def __mro_entries__(self, bases):      # class MyOperator(BaseOperator): ...
        return (_AirflowStub,)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    # task dependencies: t1 >> t2, [t1, t2] >> t3, t1 << t2
    def __rshift__(self, other):
        return other

    def __lshift__(self, other):
        return other

    __rrshift__ = __rshift__
    __rlshift__ = __lshift__

    def __iter__(self):
        return iter(())

    def __bool__(self):
        return True


def install_airflow_stub():
    """Make `import airflow...` work without Airflow. Returns True if used."""
    try:
        import airflow  # noqa: F401
        return False
    except ImportError:
        pass

    import importlib.abc
    import importlib.machinery
    import types

    class _StubModule(types.ModuleType):
        def __getattr__(self, name):
            if name.startswith('__') and name.endswith('__'):
                raise AttributeError(name)
            return _AirflowStub()

    class _Finder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
        def find_spec(self, fullname, path, target=None):
            if fullname == 'airflow' or fullname.startswith('airflow.'):
                return importlib.machinery.ModuleSpec(fullname, self, is_package=True)
            return None

        def create_module(self, spec):
            module = _StubModule(spec.name)
            module.__path__ = []
            return module

        def exec_module(self, module):
            pass

    sys.meta_path.insert(0, _Finder())
    return True
SKIP_DIRS = {'__pycache__', '.git', 'logs', 'plugins', 'node_modules', '.venv', 'venv'}


def python_files(dags_dir):
    for root, dirs, files in os.walk(dags_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
        for name in files:
            if name.endswith('.py'):
                yield Path(root) / name


def module_functions(path):
    """Names of module-level functions in a file, without executing it."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    except SyntaxError:
        return set()
    return {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def is_dag_file(path):
    text = path.read_text(encoding='utf-8', errors='replace')
    return 'airflow' in text and ('DAG(' in text or '@dag' in text)


def find_task(dags_dir, task_name):
    found = [p for p in python_files(dags_dir) if task_name in module_functions(p)]
    # Prefer the DAG file itself if the same name exists elsewhere too
    dag_files = [p for p in found if is_dag_file(p)]
    return (dag_files or found)


def load_function(path, task_name, dags_dir):
    # The DAGs folder (for `from jsonify... import`) and the DAG file's own
    # folder (for helper modules kept next to it, e.g. in airflow/)
    for folder in (str(path.parent), str(dags_dir)):
        if folder not in sys.path:
            sys.path.insert(0, folder)
    spec = importlib.util.spec_from_file_location(f'_medjsonify_{path.stem}', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, task_name)


def airflow_like_context(ds, params):
    logical_date = datetime.datetime.strptime(ds, '%Y-%m-%d').replace(tzinfo=datetime.timezone.utc)
    return {
        'ds': ds,
        'ds_nodash': ds.replace('-', ''),
        'logical_date': logical_date,
        'execution_date': logical_date,
        'params': dict(params),
        'ti': None,
    }


def call_with_context(func, context, params):
    """Pass named params, plus the Airflow context if the task accepts **kwargs."""
    sig = inspect.signature(func)
    accepts_kwargs = any(p.kind is p.VAR_KEYWORD for p in sig.parameters.values())
    kwargs = dict(params)
    for key, value in context.items():
        if accepts_kwargs or key in sig.parameters:
            kwargs.setdefault(key, value)
    if not accepts_kwargs:
        kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return func(**kwargs)


def list_tasks(dags_dir):
    # Task functions can live in the DAG files or in helper modules
    # (e.g. utils/tasks.py), so every .py file is listed.
    rows = []
    for path in python_files(dags_dir):
        for name in sorted(module_functions(path)):
            if name.endswith('_task'):
                rows.append((name, path.relative_to(dags_dir)))
    if not rows:
        print(f"No functions ending in '_task' found under {dags_dir}")
        return 1
    rows.sort(key=lambda r: (str(r[1]), r[0]))
    width = max(len(n) for n, _ in rows)
    print(f"Tasks found under {dags_dir}:")
    for name, path in rows:
        print(f"  {name:<{width}}  ({path})")
    return 0


def parse_params(items):
    params = {}
    for item in items or []:
        key, sep, value = item.partition('=')
        if not sep:
            raise SystemExit(f"--param must be key=value, got: {item}")
        params[key] = value
    return params


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('task', nargs='?', help='name of the task function in the DAG')
    ap.add_argument('--list', action='store_true', help='list the tasks found and exit')
    ap.add_argument('--dags-dir', default=DEFAULT_DAGS_DIR,
                    help=f'Airflow DAGs folder (default: {DEFAULT_DAGS_DIR})')
    ap.add_argument('--ds', default=datetime.date.today().isoformat(),
                    help='run date passed as ds, YYYY-MM-DD (default: today)')
    ap.add_argument('--param', action='append', metavar='KEY=VALUE',
                    help='extra argument for the task (repeatable)')
    args = ap.parse_args()

    # Airflow shows logging.info(); plain Python hides it unless configured
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format='%(asctime)s %(levelname)s %(message)s')

    dags_dir = Path(args.dags_dir).resolve()
    if not dags_dir.is_dir():
        print(f"ERROR: DAGs folder not found: {dags_dir}")
        return 2
    if args.list:
        return list_tasks(dags_dir)
    if not args.task:
        ap.error('give a task name, or --list')

    matches = find_task(dags_dir, args.task)
    if not matches:
        print(f"ERROR: no function '{args.task}' found under {dags_dir}")
        print("Run with --list to see the available tasks.")
        return 2
    if len(matches) > 1:
        print(f"WARNING: '{args.task}' is defined in several files; using {matches[0]}")

    path = matches[0]
    params = parse_params(args.param)
    print("=" * 60)
    print(f"Task:  {args.task}")
    print(f"File:  {path.relative_to(dags_dir)}")
    print(f"ds:    {args.ds}")
    if params:
        print(f"Params: {params}")
    print("=" * 60, flush=True)

    if install_airflow_stub():
        print("Airflow is not installed: using a stand-in to import the DAG file")

    start = time.time()
    try:
        func = load_function(path, args.task, dags_dir)
        result = call_with_context(func, airflow_like_context(args.ds, params), params)
    except Exception as e:
        traceback.print_exc()
        if "'NoneType' object has no attribute 'xcom" in str(e):
            print(f"\nERROR: {args.task} reads XCom from another task, which only exists "
                  "inside Airflow. Pass the value with --param instead.")
        print(f"\nFAILED: {args.task} after {time.time() - start:.1f}s")
        return 1

    print(f"\nDONE: {args.task} in {time.time() - start:.1f}s"
          + (f" (returned {result!r})" if result is not None else ""))
    return 0


if __name__ == '__main__':
    sys.exit(main())