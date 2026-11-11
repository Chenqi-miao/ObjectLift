"""V2 library browser; model-dependent features stay visibly pending."""
import os
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from time import perf_counter
from urllib.parse import quote

import gradio as gr

from services.library import Library
from services.embeddings import JinaEncoder
from services.indexing import IndexService
from services.captions import CaptionService, PRESET_TAGS


def build_page(library=None, encoder=None):
    library = library if library is not None else Library(os.getenv('OBJECTLIFT_DATA', 'data'))
    gr.set_static_paths(paths=[library.root / 'originals'])
    indexer = IndexService(library, encoder if encoder is not None else JinaEncoder())
    captions = CaptionService(library, indexer)
    tag_names = [*PRESET_TAGS, '未分类']
    labels = {'pending':'等待处理', 'processing':'正在处理', 'ready':'已完成', 'failed':'处理失败', 'partial':'部分完成'}

    def generation_updates(asset_id):
        started = perf_counter()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(captions.describe, asset_id)
            while True:
                try:
                    result = future.result(timeout=1)
                    yield True, f'生成完成（{perf_counter()-started:.0f} 秒）\n{result}'
                    return
                except FutureTimeout:
                    if future.done():
                        raise
                    yield False, f'正在加载模型并生成描述 / 标签……已等待 {perf_counter()-started:.0f} 秒，请勿重复点击。'

    def inspect_tags(category='全部图片'):
        rows = library.image_diagnostics()
        pending = sum(r['caption_status'] == 'pending' for r in rows)
        failed = sum(r['caption_status'] == 'failed' for r in rows)
        ready = sum(r['caption_status'] == 'ready' for r in rows)
        processing = sum(r['caption_status'] == 'processing' for r in rows)
        def searchable(row):
            return row['embedding_status'] == 'ready' and row['embedding_model'] == indexer.encoder.model_id and row['embedding_revision'] == indexer.encoder.revision
        counts = [[tag, sum(tag in r['tags'] for r in rows), sum(tag in r['tags'] and searchable(r) for r in rows)] for tag in tag_names]
        filtered = [r for r in rows if category == '全部图片' or category in r['tags'] or
                    (category == '未生成' and r['caption_status'] == 'pending') or
                    (category == '生成失败' and r['caption_status'] == 'failed') or
                    (category == '已完成但无标签' and r['caption_status'] == 'ready' and (not r['tags'] or r['tags'] == ['未分类']))]
        summary = f'全库 {len(rows)} 张图片；描述完成 {ready}，未生成 {pending}，正在加载 / 生成 {processing}，失败 {failed}。当前显示 {len(filtered)} 张。标签计数可能重叠；此处无需描述词或向量索引，语义搜索还需要就绪且兼容的向量。'
        details = [[r['original_name'], r['caption_status'], '、'.join(r['tags']) or '无', '是' if searchable(r) else '否', r['caption'] or '', r['error_message'] or ''] for r in filtered]
        gallery = [(str(library.root / r['preview_path']), r['original_name'] + ' · ' + ('、'.join(r['tags']) or '无标签')) for r in filtered]
        return summary, counts, details, gallery, filtered

    def complete_tags(category):
        pending = [r for r in library.image_diagnostics() if r['caption_status'] in ('pending', 'failed')]
        yield f'准备补齐全库 {len(pending)} 张图片；逐张处理，已完成项跳过。', *inspect_tags(category)
        yield '正在加载标签：本批次复用模型，逐张保存结果。', *inspect_tags(category)
        events = Queue()
        def produce():
            try:
                for result in captions.describe_many([r['id'] for r in pending]):
                    events.put(result)
            finally:
                events.put(None)
        failures = completed = 0
        started = perf_counter()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(produce)
            while True:
                try:
                    result = events.get(timeout=1)
                except Empty:
                    yield f'正在处理 {completed}/{len(pending)} 张 · 已用时 {perf_counter()-started:.0f} 秒', *inspect_tags(category)
                    continue
                if result is None:
                    try:
                        future.result()
                    except Exception as exc:
                        yield f'批量处理未完成：{exc}', *inspect_tags(category)
                        return
                    break
                completed += 1
                failures += int('error' in result)
                yield f"{completed}/{len(pending)} · {result.get('error', '完成')}", *inspect_tags(category)
        yield f'本轮处理结束：成功 {completed-failures}，失败 {failures} · {perf_counter()-started:.1f} 秒。', *inspect_tags(category)

    def describe_video(selected):
        if not selected:
            yield '请先选择图片或视频。'
            return
        yield '正在加载标签：准备加载本地模型并生成描述；视频基于抽样画面、不含音轨……'
        try:
            for done, update in generation_updates(selected):
                yield ('AI 生成（请核对画面）：\n' if done else '') + update
        except Exception as exc:
            yield str(exc)

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

    def retry_selected(selected, keyword, status):
        if not selected:
            yield '请先选择一项素材。', gr.skip(), gr.skip(), gr.skip()
            return
        try:
            for message in indexer.index_pending(asset_id=selected):
                gallery, assets, summary = refresh(keyword, status)
                yield message, gallery, assets, summary
        except Exception as exc:
            yield str(exc), gr.skip(), gr.skip(), gr.skip()

    def search(query, limit, media_type="全部", tag='全部'):
        try:
            hits = indexer.search(query, limit=int(limit), media_type={"图片": "image", "视频": "video"}.get(media_type), tag=None if tag == '全部' else tag)
            timing = indexer.last_search_stats if query.strip() else {}
            elapsed = timing.get('total_seconds', 0)
            cached = '（复用查询向量）' if timing.get('cache_hit') else ''
            hint = '' if hits else ' 无结果时请在标签检查区检查标签覆盖和可搜索数量；空查询请使用标签浏览。'
            return [(str(library.root / h['preview_path']),
                     f"相似度 {h['similarity']:.3f} · {h['original_name']} · {h['timestamp_ms'] / 1000 if h['timestamp_ms'] is not None else 0:.2f}s") for h in hits], [
                         [rank, h['original_name'], round(h['similarity'], 4)]
                         for rank, h in enumerate(hits, 1)
                     ], f'找到 {len(hits)} 个结果 · {elapsed:.2f} 秒{cached}；分数越高越相似，不代表概率。{hint}', [{'id': h['asset_id'], 'visual_item_id': h['visual_item_id']} for h in hits]
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
        player = ('<video controls preload="metadata" style="width:100%;max-height:480px" src="./gradio_api/file=' + quote(media, safe='/') + f'#t={seconds}"></video>') if asset['media_type'] == 'video' else ''
        frames = [(str(library.root / frame['preview_path']),
                   f"{(frame['timestamp_ms'] or 0) / 1000:.2f} 秒 · {frame['embedding_status']}")
                  for frame in asset['items']] if asset['media_type'] == 'video' else []
        frame_refs = [{'id': asset['id'], 'visual_item_id': frame['id']} for frame in asset['items']] if frames else []
        ready = sum(frame['embedding_status'] == 'ready' for frame in asset['items'])
        description = asset['description'] or {}
        description_text = (f"状态：{labels.get(description.get('status'), '尚未生成')}\n"
                            f"AI 视频摘要（基于抽样画面，不含音轨）：{description.get('caption') or '无'}\n"
                            f"采样时间（毫秒）：{description.get('timestamps') or '无'}\n"
                            f"错误：{description.get('error') or '无'}")
        if asset['media_type'] == 'image':
            description_text = f"描述状态：{labels.get(item['caption_status'], '等待处理')}\nAI 图片描述：{item['caption'] or '尚未生成'}\n自动标签：{'、'.join(item['tags']) or '尚未生成'}\n错误：{item['error_message'] or '无'}"
        return (f"命中时间：{seconds:.2f} 秒\n文件：{asset['original_name']}\n尺寸：{asset['width']} × "
                f"{asset['height']}\n状态：{labels.get(asset['status'], '等待处理')}\n"
                f"大小：{asset['size_bytes'] / 1024 / 1024:.2f} MB\n"
                f"时长：{(asset['duration_ms'] or 0) / 1000:.2f} 秒\n"
                f"画面向量完成：{ready}/{len(asset['items'])}\n"
                f"索引：{labels.get(item['embedding_status'], '等待处理')}\n"
                f"描述：{labels.get(item['caption_status'], '等待处理')}\n"
                f"错误：{item['error_message'] or '无'}",
                media, player, asset['id'], frames, frame_refs,
                str(library.root / item['preview_path']), description_text)

    from ui.workbench import build_workbench
    return build_workbench(library, indexer, locals(), tag_names)
