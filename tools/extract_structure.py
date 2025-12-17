import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT  = ROOT / 'docs' / 'system_structure.json'

CATEGORIES = {
    'Brain Capacity': [
        'brain', 'capacity', 'timestamp', 'state', 'memory', 'handler', 'core', 'manager', 'processor'
    ],
    'Knowledge': [
        'knowledge', 'graph', 'falkordb', 'store', 'record', 'data', 'planner'
    ],
    'Intelligence': [
        'intelligence', 'awareness', 'decision', 'plan', 'constraint', 'monitor', 'explore', 'sensorial', 'repeat'
    ],
}

def classify(name: str) -> str:
    t = name.lower()
    for cat, kws in CATEGORIES.items():
        if any(k in t for k in kws):
            return cat
    return 'Unclassified'

def safe_doc(node) -> str:
    try:
        return ast.get_docstring(node) or ''
    except Exception:
        return ''

def parse_file(py_path: Path) -> dict:
    src = py_path.read_text(encoding='utf-8', errors='ignore')
    tree = ast.parse(src)

    classes = {}

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            methods = []

            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    params = [
                        a.arg for a in item.args.args
                        if a.arg not in ('self', 'cls')
                    ]

                    returns = 'Any'
                    if item.returns:
                        try:
                            returns = ast.unparse(item.returns)
                        except Exception:
                            pass

                    methods.append({
                        'name': item.name,
                        'parameters': params,
                        'returns': returns,
                        'docstring': safe_doc(item).strip(),
                        'line': item.lineno,
                        'file': str(py_path.resolve())
                    })

            classes[node.name] = {
                'docstring': safe_doc(node).strip(),
                'line': node.lineno,
                'file': str(py_path.resolve()),
                'methods': methods
            }

    return {
        'file': str(py_path.resolve()),
        'classes': classes
    }

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    components = {}

    for py in ROOT.glob('*.py'):
        cat = classify(py.name)
        components.setdefault(cat, {})
        components[cat][py.name] = parse_file(py)

    OUT.write_text(json.dumps({'components': components}, indent=2), encoding='utf-8')
    print('? docs/system_structure.json generated')

if __name__ == '__main__':
    main()
