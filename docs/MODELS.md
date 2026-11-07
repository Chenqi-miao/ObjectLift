# 本地模型运行

1. 安装应用依赖和 requirements-model.txt。
2. RTX 5060 安装 CUDA 12.8 wheel：
   `uv pip install --python .venv/Scripts/python.exe torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128`
3. 依次运行 `scripts/download_embeddings.py`、`scripts/download_embedding_code.py`、`scripts/prepare_embeddings.py`。
4. 运行 `scripts/smoke_embeddings.py`，结果保存在 data/model-smoke/report.json。
5. 启动 app.py，导入图片后点击建立索引，再输入中文查询。

默认使用项目 models/jina-clip-v2，CUDA 可用时使用 GPU FP16，否则 CPU FP32。
OBJECTLIFT_DEVICE 可指定 cpu 或 cuda。模型使用固定提交版本，配置改为本地依赖，代码和配置摘要在加载前校验。仅离线推理，不上传素材。

三个纯色图片只是链路冒烟检查，不能代表真实照片的语义检索质量。自动描述与视频尚未接入。
`scripts/smoke_embeddings.py` 每次使用 data/model-smoke/时间戳/ 新建测试库，报告保存在对应 report.json。
