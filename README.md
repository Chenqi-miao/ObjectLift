# ObjectLift

从图片中发现、选择物体，生成可下载的 3D 素材。

本地 Web 图片工作台已可运行；自动检测、去背景和真实 3D 生成尚未接入。范围和验收以 [需求文档](docs/PRD.md) 为准；实测结果见 [开发日志](docs/DEVELOPMENT.md)。

图片处理模块已实现，接口见 [图片处理说明](docs/IMAGE_PROCESSING.md)。当前 Web 环境使用 Python 3.12、Pillow 11.3.0 和 Gradio 5.50.0，可独立于模型运行。

启动：`.\scripts\start.ps1`，浏览器访问 http://127.0.0.1:7860 。安装和 Docker 使用见 [Web 说明](docs/WEB.md)。

预定流程：YOLO11n（CPU）→ 裁剪 → rembg（CPU）→ TripoSR（GPU 独立进程）→ GLB 预览和下载。

开发使用 VS Code；部署目标为 Docker Linux GPU 容器，Windows Docker Desktop/WSL2 承载。先完成真实生成验证，再冻结依赖版本和实现完整界面。
