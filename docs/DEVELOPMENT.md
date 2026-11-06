# 开发日志

## 2026-11-06 · 阶段 1：环境检查

- 原始需求：PRD.md。先验证真实单图重建，再全面实现界面；视频不在本轮范围。
- 工作区：空 Git 仓库，尚无提交。
- GPU：RTX 5060 Laptop，8151 MiB，驱动 573.22，CUDA 驱动能力 12.8。检查时约占用 1.5 GiB。
- WSL2 Ubuntu：GPU 可见，Python 3.12.3，未发现 nvcc。
- Docker Desktop 已启动，引擎 29.9.2，可用内存约 15.48 GiB。
- Windows Docker CLI 不在 PATH，实际位于用户 AppData/Local/Programs/DockerDesktop/resources/bin。
- 容器 GPU 验证命令的授权请求被拒绝，因此未执行，不认定容器 GPU 可用。
- 官方 TripoSR git clone 失败：首次网络连接失败，授权后 TLS unexpected EOF。源码尚未取得。

## 验收状态

### 后续检查（迁移到 D:\WORKSPACE\practice\objectlift）

- 已确认 origin 为 https://github.com/Chenqi-miao/ObjectLift.git，main 跟踪 origin/main。
- 已获准执行容器 GPU 检查，但 ubuntu:24.04 拉取在 Docker Hub 认证阶段返回 EOF。
- 官方源码 shallow clone 仍失败：connection reset / early EOF。
- 本机现有 welcome-to-docker 镜像运行 nvidia-smi 返回 no such file or directory；不能用该结果判定 GPU 不支持。
- auth.docker.io TCP 443 检查失败，需解决下载网络；未修改系统 DNS 或代理配置。
- 新增 scripts/check_environment.ps1，供网络恢复后复测。

| 项目 | 状态 |
| --- | --- |
| Windows 与 WSL GPU 可见 | 通过 |
| Docker 引擎启动 | 通过 |
| Docker GPU 运算 | 未验证 |
| TripoSR 安装与真实生成 | 阻塞 |
| GLB 颜色与重新加载 | 未验证 |
| 连续三次任务与显存释放 | 未验证 |

## 下一步

解决官方源码下载与容器执行授权，再构建 CUDA 12.8 对应的生成环境。
先用官方示例生成网格并记录性能，随后实现 CPU 检测、去背景、独立进程生成与 Gradio 四步交互。
依赖版本须由实际安装验证后冻结，不声称当前已有可运行原型。

## 课程证据管理

### Web 前后端原型阶段

- 新增 Gradio 四步页面：上传、坐标裁剪、透明前景校验、3D 状态说明；实现 PNG 和 JSON 下载。
- 后端使用独立 UUID 目录保存处理快照，manifest 保存父任务关系，避免覆盖历史文件。
- 修改裁剪参数、上传新图及失败时清除旧的下游结果。自动检测、去背景、3D 按钮尚未启用。
- 新增启动脚本、Dockerfile、compose.yaml；容器绑定 localhost，持久化 jobs。
- Gradio 5.50.0 要求 Pillow <12，调整为 Pillow 11.3.0 后全量 11 项测试通过（0.689 秒）。
- 本地 HTTP 首页与配置已验证；scripts/smoke_web.py 实际上传→会话状态→裁剪→下载 PNG 通过。
- 系统代理会影响 localhost 检查，测试客户端使用 trust_env=False；已修复测试客户端 GBK 终端输出问题。
- 服务地址 http://127.0.0.1:7860 。未完成浏览器视觉检查、Docker 构建验证和真实模型端到端验收。

### 离线图片处理开发

- 新增 services/image_io.py：JPG/PNG 读取、EXIF 修正、像素限制、缩放、透明度保留、裁剪与检测 RGB 合成。
- 新增 services/foreground.py：前景透明通道和非空校验，不包含模型去背景。
- 新增 tests/test_images.py 的 8 个 unittest 测试方法，无外部素材依赖。
- 使用已有 Python 3.12.12 创建 .venv。WSL 和 Windows 基础 Python 均无 Pillow；离线缓存安装失败，未进行联网安装。
- 功能测试仍待 Pillow 可用后执行，使用方法见 IMAGE_PROCESSING.md。

### 图片处理阶段验证完成

- 用户授权下载小型依赖后，成功安装 Pillow 12.3.0，下载约 6.9 MiB；requirements-image.txt 已固定实测版本。
- 命令：`.venv/Scripts/python.exe -m unittest discover -s tests -v`。
- 结果：8 项测试全部通过，耗时 0.366 秒；git diff --check 通过。
- 已验证：方向修正、等比缩放、透明调色板图、像素限制、损坏及伪装格式、裁剪边距与越界、非法坐标、白背景合成和空前景。
- 限制：尚未接入 UI、检测和自动去背景；本结果不代表真实模型端到端通过。

### 网络排障补充

- 按用户要求延长超时至 900 秒、最多重试 5 次。源码曾下载到约 12.6 MB，最终仍因 TLS 中断失败，未解压或用于构建。
- Docker Hub 重试已通过认证并开始拉取 ubuntu:24.04；当前尚未确认镜像完整下载。
- 尝试使用 Git 附带 curl 的执行授权被拒绝，未执行该替代命令。
- 新增 scripts/download_triposr.ps1，保留延长超时、重试、归档解压与 SHA256 记录步骤。

- 用户提供 HTTP 代理 http://127.0.0.1:7890；仅在下载命令中显式使用，未更改系统代理。
- 代理 CONNECT 成功，但 GitHub/Docker Hub HTTPS 握手失败；代理 git clone 仍 early EOF。
- 官方 codeload 归档下载 90 秒仅约 1.2 MB/29.83 MB，超时，残留文件不作为可用源码。
- 已请用户检查代理节点。真实生成验收仍阻塞。
- 已添加 schemas.py 数据契约和 ACCEPTANCE.md 验收清单；尚未运行代码测试。

每个里程碑更新本文件：改动、命令、结果、问题、下一步。
真实任务保留 worker.log、manifest.json、耗时及峰值显存；区分替身测试和真实模型验收。
用户图片、大模型权重及生成产物不提交 Git。开发代码与文档使用阶段性提交留痕。
