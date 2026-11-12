# 本地模型运行

1. 安装应用依赖和 requirements-model.txt。
2. RTX 5060 安装 CUDA 12.8 wheel：
   `uv pip install --python .venv/Scripts/python.exe torch==2.7.1 torchvision==0.22.1 --index-url https://download.pytorch.org/whl/cu128`
3. 依次运行 `scripts/download_embeddings.py`、`scripts/download_embedding_code.py`、`scripts/prepare_embeddings.py`。
4. 运行 `scripts/smoke_embeddings.py`，结果保存在 data/model-smoke/时间戳/report.json。
5. 启动 app.py，导入图片后点击建立索引，再输入中文查询。

默认使用项目 models/jina-clip-v2，CUDA 可用时使用 GPU FP16，否则 CPU FP32。
OBJECTLIFT_DEVICE 可指定 cpu 或 cuda。模型使用固定提交版本，配置改为本地依赖，代码和配置摘要在加载前校验。仅离线推理，不上传素材。

三个纯色图片只是链路冒烟检查，不能代表真实照片的语义检索质量。视频检索使用抽样帧向量。
`scripts/smoke_embeddings.py` 每次使用 data/model-smoke/时间戳/ 新建测试库，报告保存在对应 report.json。

## 视频描述

使用 Qwen/Qwen2-VL-2B-Instruct，与现有 Transformers 4.51.3 兼容；本阶段采用该模型避免更换检索环境，替代技术路线中未安装的 Qwen3-VL 候选。
运行 `scripts/download_caption_model.py` 下载公开权重（首次解析版本后固定到 models/qwen2-vl-2b/revision.json）。推理只读取本地文件、不上传素材。

选中视频，点击“生成 / 重新生成描述与标签”。最多从已抽取画面中均匀选取 16 帧（含首尾抽样帧），按时间顺序通过原生 video 输入联合生成中文摘要；224×224 输入，不含音轨，不保证覆盖短事件。摘要与逐帧描述分开保存，不将整段摘要标为每一帧的描述，也不改变检索排序。

生成期间共享索引/搜索互斥锁，释放本进程的 Jina 模型；Qwen 在独立进程中生成后退出释放显存，600 秒超时。生成后首次新查询会重新加载 Jina。不要同时启动多个应用进程争用显存。
摘要、采样时间、模型版本、状态和错误保存在 video_descriptions 表。失败保留上次摘要并标注失败，重启可重试中断任务。OBJECTLIFT_CAPTION_PATH 可指定模型目录。

模型依据：https://huggingface.co/Qwen/Qwen2-VL-2B-Instruct 。`scripts/smoke_caption.py` 对现有素材库的一个视频做真实推理并保存摘要，结果写入 data/caption-smoke.json。
图片描述：选择图片后点击生成描述与图片标签，以原生 image 输入生成中文说明及最多5个标签。分类为人物、动物、建筑、自然、室内、交通、食物、物品。标签通过白名单校验并保存，可在语义搜索时筛选；描述不参与向量计算。

## 批次复用与算法细节（2026-11-12）

单项描述仍用独立进程；批量图片描述通过 describe_many/CaptionSession 复用同一进程和模型，逐项持久化，整个批次与检索互斥，结束关闭进程。入口位于主工作台“处理任务”和诊断页。600秒限制按单项请求计算。提示词要求最多五个标签，但代码未硬截断数量；白名单、去重、未分类规则及检索公式见 [算法说明](ALGORITHMS.md)。性能对比见 [第一轮报告](OPTIMIZATION_ROUND_1.md)，不代表命中率提升。
