# ObjectLift v2 技术路线
2026-11-06 · 一周 MVP，配套 PRD.md。候选模型尚未本机验证。

## 1. 架构
浏览器 → Gradio 页面 → Python 服务 → SQLite + 托管文件。
单个串行后台索引 worker；查询读取已就绪向量。首版不引入 Redis、Celery、独立向量数据库或 React 重写。

沿用 Python 3.12、Gradio 5.50.0、Pillow 11.3.0；新增 FFmpeg/ffprobe、sqlite3、NumPy 和模型推理依赖。PyTorch/Transformers 的实际版本在 Day 1 验证 CUDA 与模型兼容性后锁定，不沿用未验证的 3D 环境。

## 2. 模型职责与验证
| 职责 | 首个候选 | 用法 |
| --- | --- | --- |
| 中文描述/标签 | Qwen/Qwen3-VL-2B-Instruct | 逐张图片或关键帧生成一句描述和最多 5 个标签 |
| 中文图文检索 | jinaai/jina-clip-v2 | 图像和文本编码到同一空间，直接查询视觉向量 |

Qwen 官方模型卡标注 Apache-2.0。Jina 模型卡标注 CC-BY-NC-4.0，适用于本阶段非商业课程原型，未来商用需确认授权或替换。自定义模型代码审查后固定 revision，不自动跟随 main 更新。

这些是待验证候选，不是硬件运行承诺。Day 1 用 20 张图、10 条中文查询验证加载、描述正确性、JSON 解析、检索排序、时间和显存；记录全部版本。
描述 batch=1、限制输入分辨率、输出约 128 tokens 起步。生成 JSON 校验字段和标签数量，失败重试一次后记录失败，不执行模型输出的代码。

8GB 显存默认不同时驻留两个模型。描述进程批量处理后退出释放显存，向量模型优先测试 CPU 查询；需要 GPU 编码时在描述进程退出后进行。若 CPU 查询过慢，改为分阶段 GPU 索引/查询并提示等待，不争抢显存。
描述失败允许向量索引继续，显示“部分完成”，单独重试描述。
不做训练，不为查询额外调用大模型重排或聊天。API 备选需说明费用与素材外发并取得用户确认。

## 3. 入库与恢复
1. 真实格式/大小/编码校验，流式 SHA-256 去重。
2. 文件先复制到托管临时路径，完成后原子改名，再登记元数据；失败不生成可用记录。
3. 图片方向修正、缩略图生成；保留托管原始文件。
4. 视频使用 FFmpeg 定时采样，记录实际解码时间戳而非假设恒定帧率计算；保存采样版本。
5. 每单元分别写入描述、标签和向量阶段状态；推理期间不持数据库锁。
6. 完成后原子替换内存索引快照，查询不读取半更新矩阵。

启动时将中断的 processing 阶段恢复为 pending；通过唯一键复用已完成单元，重试缺失步骤。
素材列表可以展示未索引文件，只有向量 ready 的单元参与搜索。读取媒体失败时单独标错，其他素材继续。
文件孤儿可在启动检查中记录，不能未经确认删除原文件。

## 4. SQLite 三张表
主键采用 UUID，路径相对 data 根目录；时间为 UTC ISO。数据库就是默认库，不增加 libraries 表。

### assets
id TEXT PRIMARY KEY；sha256 TEXT UNIQUE NOT NULL；original_name TEXT；stored_path TEXT；
media_type TEXT；size_bytes INTEGER；width/height INTEGER；duration_ms INTEGER NULL；
status TEXT；error_code/error_message TEXT NULL；created_at/updated_at TEXT。

状态：pending / processing / ready / partial / failed，由子单元状态汇总。

### visual_items
id TEXT PRIMARY KEY；asset_id 外键；sample_index INTEGER；timestamp_ms INTEGER NULL；
preview_path TEXT；caption TEXT NULL；caption_status/embedding_status TEXT；
embedding BLOB NULL；embedding_dim INTEGER NULL；
embedding_model/embedding_revision TEXT NULL；caption_model/caption_revision TEXT NULL；
preprocess_version TEXT；error_message TEXT NULL。

唯一约束 (asset_id, sample_index)。图片 index=0、时间 NULL；视频时间为实际毫秒。
向量存 little-endian float32，校验维度、有限数值、非零范数并 L2 归一化；不用 pickle。

### tags
visual_item_id 外键；name TEXT；source TEXT。
联合主键 (visual_item_id, name)，source 首版 auto，预留 manual 不实现编辑器。

索引：assets(media_type,status)、visual_items(asset_id)、tags(name)。
启用 foreign_keys、busy_timeout，单 worker 写入；本地磁盘 WAL，禁止部署到网络共享盘。PRAGMA user_version 管理 schema 迁移。
备份用 SQLite backup API，或关闭服务后统一复制 data；不能运行中只复制 db 而遗漏 WAL。
不增加独立任务队列表，用阶段字段完成首版恢复。

## 5. 搜索
文本编码 → 归一化 → 类型/标签过滤 → NumPy 内积排序 → Top 10 → 返回画面和视频时间。
图像与查询向量必须同 model/revision/dimension；换模型必须重建，不混算旧向量。
同视频相邻 10 秒内命中保留最高分帧，远距离命中可重复展示；此规则不代表推断事件起止。
标签过滤针对命中帧，不能因为视频其他位置有某标签就认定当前帧符合。
分数为相似度，不是概率；低相关提示只提供近似结果，阈值需评测后确定。

1000×1024 float32 约 3.9MiB，仅为向量体积示例；本规模先线性扫描，不部署向量服务。

## 6. 服务接口与前端
import_files(paths)、index_pending()、list_assets(filters)、search(query,filters,limit=10)、get_asset(id)、retry_asset(id)。

SearchHit 字段：asset_id、visual_item_id、media_type、filename、preview_url、media_url、
timestamp_ms、caption、tags、similarity。媒体按 ID 映射托管路径，拒绝浏览器任意文件路径。

沿用 Gradio，改为网格/搜索/详情布局。视频跳转首先验证 HTML5 video currentTime/seeked 和 Range 请求；Gradio 不便实现时只补播放器组件，不重写整站。
Web 上传文件为托管副本；打开原素材采用下载方式，不声称浏览器能直接打开宿主机任意路径。

## 7. 目录与部署
- services/：导入、媒体、数据库、索引、搜索
- workers/：模型进程；ui/：素材页面；tests/：单测、集成、模型评测
- data/library.sqlite3、data/originals/<asset_id>/、data/previews/<asset_id>/
- models/：固定版本模型缓存；scripts/：初始化、启动、评测

Windows Python 用于现有应用开发；最终目标 WSL2 + Docker GPU 容器。先验证容器 GPU 运算，再安装模型。
优先一个 Linux 镜像加串行 worker，依赖冲突才拆应用与生成环境，以 JSON 文件协议连接。
挂载 data 和 models，默认 localhost 访问。现有 Dockerfile 仅支持旧工作台，必须升级并实测。
data、models、日志、缓存排除 Git；固定依赖、模型 revision 和镜像标签便于复现。

## 8. 验证与风险
CI 不下载模型：测试哈希去重、schema 迁移、时间索引、部分失败恢复、排序合并和维度错误，模型用明确标记的替身。
本机真实模型测试：中文描述、检索质量、速度、连续索引与显存释放。
浏览器：批量导入→状态→搜索→过滤→视频跳转→下载；HTTP 200 不代替交互验收。
Docker：构建、GPU 推理、重启持久化。性能报告区分下载/加载/推理。
视频固定抽帧会漏掉短事件，标签会出错；返回原画面供核实，不承诺事件级理解。
Day 5 功能冻结，Day 6 修问题，Day 7 演示；能力失败缩小范围，不能临时堆新模型。

## 9. 官方依据（2026-11-06 查阅）
- [Qwen3-VL-2B 模型卡](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
- [Jina CLIP v2 模型卡与许可](https://huggingface.co/jinaai/jina-clip-v2)
- [SQLite 适用场景](https://www.sqlite.org/whentouse.html)

官方模型能力与本机速度分开记录。候选选型仅基于文档，尚未完成真机验证。
