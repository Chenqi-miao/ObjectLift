from huggingface_hub import snapshot_download
snapshot_download('jinaai/jina-embeddings-v3', revision='ab036b023d30b4d1138c4c3bfa9f0c445ab455d6', local_dir='models/jina-text', allow_patterns=['config.json'])
snapshot_download('jinaai/xlm-roberta-flash-implementation', revision='bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3', local_dir='models/jina-text', allow_patterns=['*.py'])
