import json
from pathlib import Path

# Repo root (works everywhere)
ROOT = Path(__file__).resolve().parents[1]

# Input from extractor
SRC = ROOT / 'docs' / 'system_structure.json'

# Output for React UI
DST = ROOT / 'ui' / 'explorer' / 'src' / 'data' / 'system.json'

if not SRC.exists():
    raise FileNotFoundError(f'Missing input file: {SRC}')

data = json.loads(SRC.read_text(encoding='utf-8'))

modules = []

for category, files in data.get('components', {}).items():
    for filename, filedata in files.items():
        classes = []

        for cls_name, cls_data in filedata.get('classes', {}).items():
            classes.append({
                'name': cls_name,
                'docstring': cls_data.get('docstring', ''),
                'file': cls_data.get('file'),
                'line': cls_data.get('line', 1),
                'methods': cls_data.get('methods', [])
            })

        modules.append({
            'name': f'{filename} ({category})',
            'classes': classes
        })

DST.parent.mkdir(parents=True, exist_ok=True)
DST.write_text(json.dumps({'modules': modules}, indent=2), encoding='utf-8')

print('? ui/explorer/src/data/system.json generated')
