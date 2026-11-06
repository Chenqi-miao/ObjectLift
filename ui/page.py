import gradio as gr
from PIL import Image

from services.image_io import ImageValidationError
from services.workspace import Workspace


CSS = """
.gradio-container {max-width: 1180px !important; margin: auto;}
#hero {padding: 24px 8px 16px;}
#hero h1 {font-size: 38px; letter-spacing: -1px;}
.note {padding: 12px 16px; border-radius: 12px; background: #eef4f2;}
footer {display:none !important;}
"""


def build_page(root='jobs'):
    workspace = Workspace(root)
    with gr.Blocks(title='ObjectLift · 图片到 3D', theme=gr.themes.Soft(
            primary_hue='emerald', neutral_hue='slate'), css=CSS) as demo:
        gr.Markdown('# ObjectLift\n从照片中提取一个物体，为 3D 创作做好准备。', elem_id='hero')
        gr.Markdown('**图片工作台已可用** · 手动裁剪与透明前景导出\n\n'
                    '自动检测、自动去背景和 3D 重建正在接入。', elem_classes='note')
        source = gr.State(None)
        cropped = gr.State(None)
        foreground = gr.State(None)
        status = gr.Markdown('上传一张 JPG 或 PNG 开始。')
        with gr.Tabs():
            with gr.Tab('① 选择图片'):
                with gr.Row():
                    upload = gr.File(label='上传照片', file_types=['.jpg', '.jpeg', '.png'], type='filepath')
                    original = gr.Image(label='处理图片 · 方向已校正', interactive=False, type='filepath')
                gr.Markdown('当前使用手动框选。坐标以右侧处理图片的像素尺寸为准，左上角为 (0, 0)。')
            with gr.Tab('② 裁剪物体'):
                with gr.Row():
                    with gr.Column():
                        with gr.Row():
                            x1 = gr.Number(label='左 X', value=0, precision=0)
                            y1 = gr.Number(label='上 Y', value=0, precision=0)
                        with gr.Row():
                            x2 = gr.Number(label='右 X', value=0, precision=0)
                            y2 = gr.Number(label='下 Y', value=0, precision=0)
                        padding = gr.Slider(0, .5, value=.1, step=.01, label='四周边距比例')
                        crop_button = gr.Button('预览裁剪', variant='primary')
                    crop_preview = gr.Image(label='裁剪结果', interactive=False, type='filepath')
                crop_download = gr.File(label='下载裁剪 PNG', interactive=False)
            with gr.Tab('③ 确认前景'):
                gr.Markdown('上传已去背景的透明 PNG，或使用本次裁剪中的透明通道。普通照片需先去背景。')
                with gr.Row():
                    fg_upload = gr.File(label='上传透明 PNG', file_types=['.png'], type='filepath')
                    fg_preview = gr.Image(label='透明前景', image_mode='RGBA', type='filepath', interactive=False)
                use_crop = gr.Button('使用裁剪图作为前景')
                with gr.Row():
                    fg_download = gr.File(label='下载前景 PNG', interactive=False)
                    metadata = gr.File(label='下载处理说明 JSON', interactive=False)
            with gr.Tab('④ 生成 3D'):
                gr.Markdown('### 3D 重建尚未启用\nTripoSR 真机验证完成后会接入这里。'
                            '\n\n你现在可以下载前景，用于后续生成。单图重建不保证真实尺寸，背面和遮挡区域为推测。')
                gr.Button('生成 3D · 待模型接入', interactive=False)

        downstream = [cropped, crop_preview, crop_download, foreground, fg_preview, fg_download, metadata]

        def on_upload(path):
            if not path:
                return [None, None, 0, 0, 0, 0] + [None] * 7 + ['上传一张 JPG 或 PNG 开始。']
            try:
                result = workspace.upload(path)
                with Image.open(result['image']) as image:
                    w, h = image.size
                return [result, result['image'], 0, 0, w, h] + [None] * 7 + [f'图片已就绪：{w} × {h} 像素。进入第②步调整裁剪。']
            except (ImageValidationError, OSError) as exc:
                return [None, None, 0, 0, 0, 0] + [None] * 7 + [f'上传失败：{exc}']

        upload.change(on_upload, upload, [source, original, x1, y1, x2, y2] + downstream + [status])

        def do_crop(src, left, top, right, bottom, pad):
            try:
                if not src:
                    raise ImageValidationError('请先上传图片。')
                if None in (left, top, right, bottom):
                    raise ImageValidationError('请填写完整裁剪坐标。')
                result = workspace.crop(src, (left, top, right, bottom), pad)
                return [result, result['image'], result['image']] + [None] * 4 + ['裁剪完成。进入第③步确认前景。']
            except (ValueError, OSError) as exc:
                return [None] * 7 + [f'裁剪失败：{exc}']

        crop_button.click(do_crop, [source, x1, y1, x2, y2, padding], downstream + [status])
        for component in [x1, y1, x2, y2, padding]:
            component.input(lambda: [None] * 7 + ['裁剪参数已修改，请重新预览裁剪。'],
                            outputs=downstream + [status])

        def prepare(path, crop, from_crop):
            try:
                if from_crop and not crop:
                    raise ImageValidationError('请先完成裁剪。')
                selected = crop['image'] if from_crop else path
                if not selected:
                    return None, None, None, None, '请选择透明 PNG。'
                result = workspace.foreground(selected, crop['id'] if crop else None)
                return result, result['image'], result['image'], result['manifest'], '前景已就绪，可以下载。3D 重建尚未接入。'
            except (ImageValidationError, OSError) as exc:
                return None, None, None, None, f'前景校验失败：{exc}'

        fg_outputs = [foreground, fg_preview, fg_download, metadata, status]
        fg_upload.change(lambda p, c: prepare(p, c, False), [fg_upload, cropped], fg_outputs)
        use_crop.click(lambda c: prepare(None, c, True), cropped, fg_outputs)
    return demo.queue(default_concurrency_limit=1)
