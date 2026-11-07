"""Local Jina adapter. No weights are downloaded during application startup."""
import os
import re
import json
import hashlib
from pathlib import Path


class JinaEncoder:
    model_id = 'jinaai/jina-clip-v2'

    def __init__(self):
        self.revision = os.getenv('OBJECTLIFT_EMBEDDING_REVISION', 'e10d47f5691d0454a0fb5d13f46f2199b74cb436')
        self.path = os.getenv('OBJECTLIFT_EMBEDDING_PATH', str(Path(__file__).resolve().parents[1] / 'models' / 'jina-clip-v2'))
        self.model = None

    def load(self):
        if self.model is None:
            if not self.path or not re.fullmatch(r'[0-9a-f]{40}', self.revision):
                raise ValueError('请配置本地模型目录 OBJECTLIFT_EMBEDDING_PATH 和已审查的 40 位提交版本 OBJECTLIFT_EMBEDDING_REVISION。')
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            os.environ['HF_MODULES_CACHE'] = str(Path(self.path).parent / 'module-cache')
            from transformers import AutoModel
            import torch
            manifest_path = Path(self.path) / 'local-manifest.json'
            if not manifest_path.exists():
                raise ValueError('本地模型未准备完成，请先运行下载和 prepare_embeddings.py 脚本。')
            manifest = json.loads(manifest_path.read_text())
            if manifest['revision'] != self.revision:
                raise ValueError('本地模型版本不一致。')
            for relative, digest in manifest['files'].items():
                file = Path(self.path).parent / relative
                if hashlib.sha256(file.read_bytes()).hexdigest() != digest:
                    raise ValueError(f'模型配置或代码已变更：{relative}')
            device = os.getenv('OBJECTLIFT_DEVICE', 'cuda' if torch.cuda.is_available() else 'cpu')
            os.environ['HF_HUB_OFFLINE'] = '1'
            os.environ['TRANSFORMERS_OFFLINE'] = '1'
            self.model = AutoModel.from_pretrained(
                self.path, trust_remote_code=True, local_files_only=True,
                torch_dtype=torch.float16 if device == 'cuda' else torch.float32,
                revision=self.revision).to(device).eval()
        return self.model

    def image(self, path):
        from services.image_io import load_image, detection_rgb
        image = detection_rgb(load_image(path))
        return self.load().encode_image([image], batch_size=1)[0]

    def unload(self):
        if self.model is not None:
            self.model = None
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    def text(self, query):
        return self.load().encode_text([query])[0]
