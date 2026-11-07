"""Download public caption weights once; retain the resolved revision for retries."""
import json
import os
from pathlib import Path
os.environ.setdefault('HF_HUB_DISABLE_XET', '1')
from huggingface_hub import HfApi, snapshot_download

root = Path(__file__).resolve().parents[1] / 'models' / 'qwen2-vl-2b'
root.mkdir(parents=True, exist_ok=True)
manifest = root / 'revision.json'
model_id = 'Qwen/Qwen2-VL-2B-Instruct'
revision = json.loads(manifest.read_text())['revision'] if manifest.exists() else HfApi().model_info(model_id).sha
manifest.write_text(json.dumps({'model_id': model_id, 'revision': revision}), encoding='utf-8')
snapshot_download(model_id, revision=revision, local_dir=root,
                  allow_patterns=['*.json', '*.safetensors', '*.txt', '*.model'], max_workers=2)
(root / 'ready.json').write_text(json.dumps({'revision': revision}), encoding='utf-8')
print('Caption model ready:', revision, flush=True)
