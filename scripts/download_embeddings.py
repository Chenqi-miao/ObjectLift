"""Download pinned public model artifacts; never uploads user assets."""
from huggingface_hub import snapshot_download

if __name__ == '__main__':
    snapshot_download('jinaai/jina-clip-implementation', revision='39e6a55ae971b59bea6e44675d237c99762e7ee2', local_dir='models/jina-code', allow_patterns=['*.py'])
    snapshot_download('jinaai/jina-clip-v2', revision='e10d47f5691d0454a0fb5d13f46f2199b74cb436', local_dir='models/jina-clip-v2', allow_patterns=['*.json', 'model.safetensors'], max_workers=2)
