import json
from pathlib import Path

src = Path(r'C:/Users/Ateeb/Desktop/tmrl_docker_trainer/ui/explorer/src/data/system.json')
dst = Path(r'C:/Users/Ateeb/Desktop/tmrl_docker_trainer/ui/explorer/src/data/system.normalized.json')

raw = json.loads(src.read_text())

modules = []

for category, files in raw.get('components', {}).items():
    for filename, filedata in files.items():
        classes = []
        for cls_name, cls_data in filedata.get('classes', {}).items():
            classes.append({
                'name': cls_name,
                'methods': cls_data.get('methods', [])
            })

        modules.append({
            'name': f'{filename} ({category})',
            'classes': classes
        })

dst.write_text(json.dumps({'modules': modules}, indent=2))
print('normalized modules:', len(modules))
