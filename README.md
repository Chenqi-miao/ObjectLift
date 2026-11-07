# ObjectLift

本地视觉素材整理与检索工具：导入图片和短视频，自动描述与分类，用中文搜索素材并定位视频画面。

当前入口为新版素材库：支持图片批量托管导入、去重、向量索引与失败重试、中文搜索、文件名和入库状态筛选、状态统计，以及从素材库或搜索结果查看详情和下载原图。搜索支持回车提交和调整结果数量。已接入 H.264 MP4 导入（300MB / 3 分钟）、约每 5 秒抽帧、视频帧检索、类型筛选和定位播放器入口；需本地 FFmpeg，浏览器跳转仍待验收。自动描述尚未接入，检索准确率仍待优化。新版范围以 [PRD](docs/PRD.md) 和 [技术路线](docs/TECHNICAL_PLAN.md) 为准；历史实测结果见 [开发日志](docs/DEVELOPMENT.md)。3D 方向暂停，旧方案保存在 docs/archive。

图片处理模块已实现，接口见 [图片处理说明](docs/IMAGE_PROCESSING.md)。当前 Web 环境使用 Python 3.12、Pillow 11.3.0 和 Gradio 5.50.0，可独立于模型运行。

启动：`.\scripts\start.ps1`，浏览器访问 http://127.0.0.1:7860 。安装和 Docker 使用见 [Web 说明](docs/WEB.md)。

新版流程：托管导入 → 图片/视频关键帧 → 描述与标签、图文向量 → SQLite → 中文检索 → 图片预览/视频跳转。

开发使用 VS Code；部署目标为 Docker Linux GPU 容器，Windows Docker Desktop/WSL2 承载。先验证模型质量和速度，再冻结推理依赖；现有 Dockerfile 尚未包含新版模型。
