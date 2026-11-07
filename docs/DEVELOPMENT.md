# 开发日志

## 2026-11-06 · v2 图片素材库首批实现

- 新增 services/library.py：SQLite 三表、schema 版本、WAL、托管图片与缩略图、流式哈希去重、逐文件错误隔离；提供中断阶段恢复接口。
- app.py 切换至新版素材库页面：批量图片导入、网格、元数据详情和托管原文件下载。旧工作台代码保留。
- compose 增加 data/models 挂载，data 排除 Git。
- 全量 unittest 13 项通过，包含新增去重、重启、原文件保留、失败隔离与阶段恢复测试。沙箱不能访问已有解释器，获授权后使用原虚拟环境运行成功。
- 自动描述、向量检索、视频导入及后台 worker 尚未接入；当前素材显示 pending。真实模型、浏览器交互及新版容器尚未验收。

## 2026-11-06 · 产品方向重新确定

- 新目标：一周完成本地视觉素材库，支持图片/短视频、自动描述与标签、中文检索和视频时间定位。
- 3D 暂停；旧 PRD 与验收清单归档至 docs/archive，不删除既有代码和测试记录。
- 新增 TECHNICAL_PLAN.md，更新 PRD.md、ACCEPTANCE.md 和 README。
- 数据库规划为 assets、visual_items、tags 三表；SQLite 存向量，NumPy 检索。
- Qwen3-VL-2B 与 Jina CLIP v2 为待验证候选；模型版本、许可与实际显存需按技术路线核实，尚未安装验证。
- 本次仅重拟文档，未将旧图片工作台标成新功能已完成。

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

## 2026-11-06 · 图片向量索引链路第一阶段

- 接入本地 Jina 适配器、串行索引、逐项失败重试、归一化 float32 持久化、同模型版本检索和 UI 进度反馈。
- 页面新增“建立索引 / 重试失败项”和中文语义搜索；描述尚未完成时素材标记 partial。
- 配置 OBJECTLIFT_EMBEDDING_PATH 为已审查的本地模型目录，OBJECTLIFT_EMBEDDING_REVISION 为对应 40 位提交 SHA。仅本地加载，不自动下载或上传素材。目录内容与声明版本的一致性目前由部署者保证。
- 全量 unittest 15 项通过；新版 Gradio Blocks 构建通过。新增测试使用明确的测试编码器，覆盖失败重试、持久化、版本隔离、无效向量；不代表真实模型验收。
- 环境检查：torch、transformers、timm 均未安装，models 目录为空。真实模型推理、检索质量与浏览器交互尚未验收。
- 自动描述、标签、视频处理仍未接入。本次完成的是索引基础链路，不是整个技术路线。
- 下一阶段：准备独立模型环境，固定并审查 Jina 自定义代码和权重版本，安装兼容依赖后运行真实中文查询评测；再接入 Qwen 描述进程。

## 2026-11-06 · 真实 Jina CPU 链路验证

- 下载固定权重 e10d47f5691d0454a0fb5d13f46f2199b74cb436（model.safetensors 1,730,688,642 字节）。
- 固定主实现 39e6a55ae971b59bea6e44675d237c99762e7ee2、文本配置 ab036b023d30b4d1138c4c3bfa9f0c445ab455d6 和文本实现 bd55a5ec8e6c0fb1d6c26efb4b6a4a74ce8a88d3。
- 检查嵌套配置和加载路径，改成本地依赖，关闭 FlashAttention/xformers；修复 Transformers 本地嵌套模块缓存遗漏。配置和源码哈希在加载前校验。
- 真实 CPU 测试：三张纯色图索引和中文查询总计 16.307 秒，红图排名第一（0.31284），蓝图 0.23824、绿图 0.21756。不是检索质量评测。
- 回归 15 项通过。GPU 版 PyTorch 正在安装，显存与 GPU 耗时尚未确认。
- 操作步骤见 MODELS.md；自动描述、标签和视频仍未实现。

### RTX 5060 8GB 实测通过

- 已安装 torch 2.7.1+cu128 / torchvision 0.22.1+cu128，CUDA 可用，设备为 NVIDIA GeForce RTX 5060 Laptop GPU。
- GPU FP16：三张纯色图片新建索引并查询成功，红图排第一。首次冷启动测试 61.789 秒（含依赖加载）；重复启动测试同链路 7.262 秒；已加载模型后的单条查询 0.0738 秒。计时不含下载，不代表大规模照片性能。
- PyTorch 峰值 allocated 2637.94 MiB，reserved 2822 MiB；不包括桌面及其他程序显存，也不是 nvidia-smi 总占用。
- 最终 CUDA 环境下全量 15 项回归通过。真实照片检索质量、浏览器交互、描述和视频尚待验收。

## 2026-11-07 视频接入
新增 H.264 MP4 托管导入（300MB / 180 秒）、每约 5 秒抽样和实际帧时间戳、视频帧向量索引、10 秒内相邻命中合并、搜索类型筛选、命中时间和播放器入口。18 项回归通过；解码替身测试不代表真实视频或浏览器定位验收。
FFmpeg 可放置 tools/ffmpeg/<发行目录>/bin，或使用 PATH / OBJECTLIFT_FFMPEG 和 OBJECTLIFT_FFPROBE。抽帧规则依据 https://www.ffmpeg.org/ffmpeg-filters.html 的 select 与 showinfo。

真实 FFmpeg 验证通过：scripts/smoke_video.py 生成 12 秒 H.264，成功入库、哈希去重并产出 0 / 5000 / 10000ms 三帧。FFmpeg 已下载至项目 tools 目录并自动发现。浏览器播放定位、真实模型视频检索质量与 Docker 构建尚未验收。
