import json
from pathlib import Path

ROOT = Path(r'C:/Users/Ateeb/Desktop/tmrl_docker_trainer')
SRC  = Path(r'C:/Users/Ateeb/Desktop/tmrl_docker_trainer/ui/explorer/src/data/system.json')

data = json.loads(SRC.read_text())

# build filename -> full path lookup
file_index = {}
for p in ROOT.rglob('*.py'):
    file_index[p.name] = p

for module in data['modules']:
    filename = module['name'].split(' ')[0]

    real_path = file_index.get(filename)
    if not real_path:
        continue

    for cls in module.get('classes', []):
        cls['file'] = str(real_path)
        cls.pop('line', None)

        for m in cls.get('methods', []):
            m['file'] = str(real_path)
            m.pop('line', None)

SRC.write_text(json.dumps(data, indent=2))
print('? Real file paths injected (line numbers removed)')
