"""V2 library browser; model-dependent features stay visibly pending."""
import os
from urllib.parse import quote

import gradio as gr

from services.library import Library
from services.embeddings import JinaEncoder
from services.indexing import IndexService


def build_page(library=None, encoder=None):
    library = library if library is not None else Library(os.getenv('OBJECTLIFT_DATA', 'data'))
    gr.set_static_paths(paths=[library.root / 'originals'])
    indexer = IndexService(library, encoder if encoder is not None else JinaEncoder())

    def warmup():
        yield '正在加载本地模型并预热搜索，首次可能需要约一分钟……'
        try:
            elapsed = indexer.warmup()
            yield f'搜索预热完成，用时 {elapsed:.2f} 秒。服务保持运行时可复用模型。'
        except Exception as exc:
            yield str(exc)

    def index(keyword, status):
        for message in indexer.index_pending():
            gallery, assets, summary = refresh(keyword, status)
            yield message, gallery, assets, summary

    def search(query, limit, media_type="全部"):
        try:
            hits = indexer.search(query, limit=int(limit), media_type={"图片": "image", "视频": "video"}.get(media_type))
            timing = indexer.last_search_stats if query.strip() else {}
            elapsed = timing.get('total_seconds', 0)
            cached = '（复用查询向量）' if timing.get('cache_hit') else ''
            return [(str(library.root / h['preview_path']),
                     f"相似度 {h['similarity']:.3f} · {h['original_name']} · {h['timestamp_ms'] / 1000 if h['timestamp_ms'] is not None else 0:.2f}s") for h in hits], [
                         [rank, h['original_name'], round(h['similarity'], 4)]
                         for rank, h in enumerate(hits, 1)
                     ], f'找到 {len(hits)} 个结果 · {elapsed:.2f} 秒{cached}；分数越高越相似，不代表概率。', [{'id': h['asset_id'], 'visual_item_id': h['visual_item_id']} for h in hits]
        except Exception as exc:
            return [], [], str(exc), []

    def refresh(keyword='', status='全部'):
        assets = library.list_assets(keyword=keyword, status=None if status == '全部' else status)
        gallery = []
        for asset in assets:
            item = library.get_asset(asset['id'])['items'][0]
            gallery.append((str(library.root / item['preview_path']),
                            asset['original_name'] + ' · ' + asset['status']))
        stats = library.statistics()
        summary = f"共 {stats['total']} 项 · 已有向量 {stats['searchable']} 项 · 失败 {stats.get('failed', 0)} 项 · 当前显示 {len(assets)} 项。部分完成表示向量已就绪、自动描述尚未完成。"
        return gallery, assets, summary

    def upload(paths, keyword, status):
        results = library.import_files(paths or [])
        gallery, assets, summary = refresh(keyword, status)
        return results, gallery, assets, summary

    def select(assets, event: gr.SelectData):
        asset = library.get_asset(assets[event.index]['id'])
        selected = assets[event.index]
        item = next((i for i in asset['items'] if i['id'] == selected.get('visual_item_id')), asset['items'][0])
        seconds = (item['timestamp_ms'] or 0) / 1000
        media = str(library.root / asset['stored_path'])
        player = ('<video controls preload="metadata" style="width:100%;max-height:480px" src="/gradio_api/file=' + quote(media, safe='/') + f'#t={seconds}"></video>') if asset['media_type'] == 'video' else ''
        return (f"命中时间：{seconds:.2f} 秒\n文件：{asset['original_name']}\n尺寸：{asset['width']} × "
                f"{asset['height']}\n状态：{asset['status']}\n"
                f"向量：{item['embedding_status']}\n"
                f"描述：{item['caption_status']}\n"
                f"错误：{item['error_message'] or '无'}",
                media, player)

    with gr.Blocks(title='ObjectLift 素材库') as page:
        gr.Markdown('# ObjectLift\n本地视觉素材库 · v2 开发版')
        gr.Markdown('图片 / H.264 MP4 导入 → 建立向量索引 → 中文搜索。视频上限 300MB / 4 分钟，每 5 秒抽帧；自动描述尚未接入。')
        assets = gr.State([])
        hits = gr.State([])
        summary = gr.Textbox(label='素材库概况', interactive=False)
        with gr.Row():
            keyword = gr.Textbox(label='按文件名筛选（包含匹配）')
            status = gr.Dropdown(['全部', 'pending', 'processing', 'partial', 'ready', 'failed'], value='全部', label='入库状态')
            refresh_button = gr.Button('刷新素材库')
        files = gr.File(label='批量选择图片或视频', file_count='multiple',
                        file_types=['.jpg', '.jpeg', '.png', '.mp4'], type='filepath')
        button = gr.Button('导入素材', variant='primary')
        result = gr.JSON(label='逐文件导入结果')
        gallery = gr.Gallery(label='素材库', columns=4, type='filepath')
        index_button = gr.Button('建立索引 / 重试失败项')
        progress = gr.Textbox(label='索引进度', interactive=False)
        query = gr.Textbox(label='用中文描述要找的画面')
        gr.Markdown('服务重启后的首次搜索需要加载模型，可能约一分钟；可先点击预热搜索。后续查询复用模型。')
        warmup_button = gr.Button('预热搜索')
        warmup_status = gr.Textbox(label='模型预热状态', interactive=False)
        limit = gr.Slider(1, 50, value=10, step=1, label='返回结果数量')
        media_type = gr.Dropdown(['全部', '图片', '视频'], value='全部', label='搜索素材类型')
        search_button = gr.Button('语义搜索')
        search_results = gr.Gallery(label='搜索结果', columns=4, type='filepath')
        search_scores = gr.Dataframe(
            headers=['排名', '文件名', '相似度'], datatype=['number', 'str', 'number'],
            value=[], label='搜索结果分数（按相似度降序）', interactive=False)
        search_status = gr.Textbox(label='搜索状态', interactive=False)
        detail = gr.Textbox(label='素材详情', interactive=False)
        player = gr.HTML(label='视频定位预览')
        download = gr.File(label='下载托管原文件', interactive=False)
        button.click(upload, [files, keyword, status], [result, gallery, assets, summary])
        warmup_button.click(warmup, outputs=warmup_status)
        gallery.select(select, assets, [detail, download, player])
        search_results.select(select, hits, [detail, download, player])
        index_button.click(index, [keyword, status], [progress, gallery, assets, summary], concurrency_limit=1)
        search_button.click(search, [query, limit, media_type], [search_results, search_scores, search_status, hits])
        query.submit(search, [query, limit, media_type], [search_results, search_scores, search_status, hits])
        for trigger in (keyword.submit, status.change, refresh_button.click):
            trigger(refresh, [keyword, status], [gallery, assets, summary])
        page.load(refresh, outputs=[gallery, assets, summary])
    return page
