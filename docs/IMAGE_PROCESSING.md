# 图片处理模块

## 接口

- `load_image(path, max_side=2048, max_pixels=40000000)`：按真实格式接受静态 JPG/PNG，拒绝损坏图及超大图，修正 EXIF 方向，等比缩小但不放大，返回独立 RGB/RGBA 图片。保留透明通道。
- `crop_bounds(image, bbox, padding_ratio=0.1)`：框为 `(x1,y1,x2,y2)`，右下边界不包含在裁剪内。按框宽高向四边扩展，向外取整并限制到图片范围。倒置、空框、非有限坐标、完全位于图外的框会报错。
- `crop_target(...)`：使用上述坐标生成裁剪图，保留颜色模式和透明度。
- `detection_rgb(image)`：透明图合成白背景 RGB 副本，用于后续检测，不改变尺寸或原图。
- `validate_foreground(image)`：验证透明通道、最小尺寸和非空 alpha，返回 RGBA 副本。完全不透明的 RGBA 可通过，但不代表去背景质量合格。

所有检测和裁剪坐标必须基于 `load_image` 返回的图片，不使用原始文件或浏览器缩略图的坐标。界面坐标映射将在 UI 接入时实现。

本模块不执行自动去背景，也不做 TripoSR 的居中和背景合成，避免重复预处理。

## 运行测试

已有 Pillow 时无需联网：

```powershell
.venv/Scripts/python.exe -m unittest discover -s tests -v
```

若缺少 Pillow，网络恢复后先安装：

```powershell
uv pip install --python .venv/Scripts/python.exe -r requirements-image.txt
```

测试用例自行生成小图片，不下载模型或测试素材。覆盖 EXIF、尺寸限制、调色板透明度、损坏和格式伪装、裁剪越界、边距、非有限框、透明背景合成与空前景。

2026-11-06 实测：Windows Python 3.12.12 + Pillow 12.3.0，以上 8 项测试全部通过（0.366 秒）。测试使用生成的小图片，真实用户图片与 UI 接入仍需集成验收。

Web 接入后，为兼容 Gradio 5.50.0，将 Pillow 固定为 11.3.0；全量 11 项测试及 HTTP 上传裁剪下载冒烟测试已通过。
