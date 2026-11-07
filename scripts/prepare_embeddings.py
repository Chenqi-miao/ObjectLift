"""Localize pinned upstream code/configs; run after both download scripts."""
import hashlib
import json
import shutil
from pathlib import Path

root = Path(__file__).resolve().parents[1] / 'models'
model = root / 'jina-clip-v2'
text = root / 'jina-text'
for name in ('tokenizer.json', 'tokenizer_config.json', 'special_tokens_map.json'):
    shutil.copy2(model / name, text / name)
for path in (root / 'jina-code').glob('*.py'):
    shutil.copy2(path, model / path.name)
for path in (model / 'config.json', model / 'preprocessor_config.json', text / 'config.json'):
    data = json.loads(path.read_text())
    data['auto_map'] = {key: value.split('--')[-1] for key, value in data['auto_map'].items()}
    if path == model / 'config.json':
        data['text_config']['hf_model_name_or_path'] = str(text)
        data['use_text_flash_attn'] = False
        data['use_vision_xformers'] = False
    path.write_text(json.dumps(data, indent=2), encoding='utf-8')
manifest = {'revision': 'e10d47f5691d0454a0fb5d13f46f2199b74cb436', 'files': {}}
cache = root / 'module-cache' / 'transformers_modules'
cache.mkdir(parents=True, exist_ok=True)
(cache / '__init__.py').touch()
for folder in (model, text):
    target = cache / folder.name
    target.mkdir(exist_ok=True)
    (target / '__init__.py').touch()
    for source in folder.glob('*.py'):
        shutil.copy2(source, target / source.name)
    for path in sorted(folder.glob('*')):
        if path.suffix in ('.py', '.json') and path.name != 'local-manifest.json':
            manifest['files'][str(path.relative_to(root))] = hashlib.sha256(path.read_bytes()).hexdigest()
(model / 'local-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print('Local configuration prepared')
