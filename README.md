# ObjectLift

从图片中发现、选择物体，生成可下载的 3D 素材。

当前处于环境验证阶段，尚未完成可运行原型。范围和验收以 [需求文档](docs/PRD.md) 为准；实测结果见 [开发日志](docs/DEVELOPMENT.md)。

图片处理模块已实现并通过 8 项单元测试，接口及测试命令见 [图片处理说明](docs/IMAGE_PROCESSING.md)。使用 Python 3.12 和 Pillow 12.3.0，可独立于模型运行。

预定流程：YOLO11n（CPU）→ 裁剪 → rembg（CPU）→ TripoSR（GPU 独立进程）→ GLB 预览和下载。

开发使用 VS Code；部署目标为 Docker Linux GPU 容器，Windows Docker Desktop/WSL2 承载。先完成真实生成验证，再冻结依赖版本和实现完整界面。
