# 本地 Web 原型

架构：浏览器 → Gradio Web 服务 → Python services → jobs 独立处理目录。
前端通过 Gradio 事件调用 Python 后端。当前不需要另启 Node.js 服务，也不需要 GPU。

## 启动

在项目根目录执行：

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv/Scripts/python.exe -r requirements-app.txt
.\scripts\start.ps1
```

已有虚拟环境时跳过创建。浏览器打开 http://127.0.0.1:7860 。停止服务按 Ctrl+C。

## 操作

1. 上传 JPG/PNG，查看方向修正后的图片和像素尺寸。
2. 输入裁剪框四个坐标，调整边距，点击预览裁剪。默认框覆盖全图。
3. 上传已去背景的透明 PNG，或在原图本来透明时使用裁剪图作为前景。
4. 下载裁剪、前景和处理说明 JSON。3D 按钮等待真实模型验证后启用。

上传限制 20 MB。修改裁剪参数即清除下游结果；上传新图会清除旧任务结果。
每次处理保存独立目录，不覆盖历史文件。jobs 目录可能包含个人照片，已排除 Git。
当前历史文件不会自动删除；关闭服务后可以自行清理不需要的 jobs 子目录。

## Docker

```powershell
docker compose up --build
```

compose 默认绑定本机地址，数据保存到项目 jobs 目录。本镜像仅包含图片工作台，不包含 TripoSR 或 CUDA。
局域网共享需另外配置监听地址及端口；当前不创建公网分享链接。

## 验证

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

图片模块、处理目录隔离和页面回调都纳入测试。Docker 构建与真实模型端到端验收单独记录。
