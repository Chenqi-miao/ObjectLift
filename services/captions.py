"""Persist asset-level summaries separately from frame captions."""
import json
import os
import subprocess
import sys
import threading
from types import SimpleNamespace
from services.caption_session import CaptionSession
from pathlib import Path
from tempfile import TemporaryDirectory
from datetime import datetime, timezone

PRESET_TAGS = ['人物', '动物', '建筑', '自然', '室内', '交通', '食物', '物品']


def normalize_tags(tags):
    if tags is None:
        return ['未分类']
    if not isinstance(tags, list) or any(not isinstance(t, str) for t in tags):
        raise ValueError('标签必须是字符串数组。')
    known = list(dict.fromkeys(t.strip() for t in tags if t.strip() in PRESET_TAGS))
    return known[:5] or ['未分类']


class CaptionService:
    def __init__(self, library, indexer):
        self.library, self.indexer = library, indexer
        self.model_path = Path(os.getenv('OBJECTLIFT_CAPTION_PATH', str(Path(__file__).resolve().parents[1] / 'models/qwen2-vl-2b')))

    def describe(self, asset_id):
        if not self.indexer.lock.acquire(blocking=False):
            raise ValueError('模型正在处理其他任务，请稍后重试。')
        try:
            asset = self.library.get_asset(asset_id)
            manifest = self.model_path / 'revision.json'
            if not manifest.exists():
                raise ValueError('请先运行 scripts/download_caption_model.py 下载描述模型。')
            revision = json.loads(manifest.read_text(encoding='utf-8'))['revision']
            ready = self.model_path / 'ready.json'
            if not ready.exists() or json.loads(ready.read_text(encoding='utf-8')).get('revision') != revision:
                raise ValueError('视频描述模型下载尚未完成，请运行 scripts/download_caption_model.py 续传。')
            items = asset['items']
            count = min(16, len(items))
            sampled = [items[round(i * (len(items)-1) / max(1, count-1))] for i in range(count)]
            if not sampled:
                raise ValueError('视频没有可用抽样帧。')
            self.save(asset_id, 'processing', revision=revision)
            try:
                if hasattr(self.indexer.encoder, 'unload'):
                    self.indexer.encoder.unload()
                with TemporaryDirectory(prefix='caption-', dir=self.library.root) as temporary:
                    request, output = Path(temporary) / 'request.json', Path(temporary) / 'result.json'
                    frames = [{'path': str(self.library.root / item['preview_path']), 'timestamp_ms': item['timestamp_ms']} for item in sampled]
                    request.write_text(json.dumps({'model_path': str(self.model_path), 'media_type': asset['media_type'], 'duration_ms': asset['duration_ms'], 'frames': frames}), encoding='utf-8')
                    env = {**os.environ, 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'}
                    result = getattr(self, '_run', subprocess.run)([sys.executable, str(Path(__file__).with_name('caption_worker.py')), str(request), str(output)],
                        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600, env=env,
                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
                    if result.returncode:
                        raise ValueError('描述生成失败：' + result.stderr[-1500:])
                    generated = json.loads(output.read_text(encoding='utf-8'))
                    if 'error' in generated:
                        raise ValueError(generated['error'])
                    caption = generated['caption']
                    if not isinstance(caption, str) or not caption.strip():
                        raise ValueError('描述结果无效。')
                    tags = generated.get('tags') if asset['media_type'] == 'image' else []
                    if asset['media_type'] == 'image':
                        tags = normalize_tags(tags)
                self.save(asset_id, 'ready', caption, revision, [i['timestamp_ms'] for i in sampled], tags=tags)
                return caption + ('\n标签：' + '、'.join(tags) if tags else '')
            except Exception as exc:
                self.save(asset_id, 'failed', revision=revision, error=str(exc))
                raise
        finally:
            self.indexer.lock.release()

    def describe_many(self, asset_ids):
        if not asset_ids:
            return
        if not self.indexer.lock.acquire(blocking=False):
            raise ValueError('模型正在处理其他任务，请稍后重试。')
        try:
            if hasattr(self.indexer.encoder, 'unload'):
                self.indexer.encoder.unload()
            with CaptionSession(self.library.root) as session:
                isolated = CaptionService(self.library, SimpleNamespace(lock=threading.Lock(), encoder=None))
                isolated.model_path = self.model_path
                isolated._run = session.run
                for asset_id in asset_ids:
                    try:
                        yield {'id': asset_id, 'output': isolated.describe(asset_id)}
                    except Exception as exc:
                        yield {'id': asset_id, 'error': str(exc)}
        finally:
            self.indexer.lock.release()

    def save(self, asset_id, status, caption=None, revision=None, timestamps=None, error=None, tags=None):
        with self.library.connection() as db:
            asset = db.execute('SELECT media_type FROM assets WHERE id=?', (asset_id,)).fetchone()
            if asset['media_type'] == 'image':
                db.execute('UPDATE visual_items SET caption_status=?,caption=COALESCE(?,caption),caption_model=?,caption_revision=?,error_message=? WHERE asset_id=?', (status, caption, 'Qwen/Qwen2-VL-2B-Instruct', revision, error, asset_id))
                if status == 'ready':
                    tags = normalize_tags(tags)
                    item = db.execute('SELECT id FROM visual_items WHERE asset_id=?', (asset_id,)).fetchone()['id']
                    db.execute("DELETE FROM tags WHERE visual_item_id=? AND source='auto'", (item,))
                    db.executemany('INSERT OR IGNORE INTO tags (visual_item_id,name,source) VALUES (?,?,?)', [(item, t, 'auto') for t in dict.fromkeys(tags or [])])
                state = db.execute('SELECT embedding_status FROM visual_items WHERE asset_id=?', (asset_id,)).fetchone()[0]
                overall = 'ready' if state == status == 'ready' else ('partial' if 'ready' in (state, status) else status)
                db.execute('UPDATE assets SET status=?,updated_at=? WHERE id=?', (overall, datetime.now(timezone.utc).isoformat(), asset_id))
                return
            db.execute('INSERT INTO video_descriptions (asset_id,status,caption,model,revision,timestamps,error,updated_at) VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(asset_id) DO UPDATE SET status=excluded.status,caption=COALESCE(excluded.caption,video_descriptions.caption),model=excluded.model,revision=excluded.revision,timestamps=COALESCE(excluded.timestamps,video_descriptions.timestamps),error=excluded.error,updated_at=excluded.updated_at',
                (asset_id, status, caption, 'Qwen/Qwen2-VL-2B-Instruct', revision, json.dumps(timestamps) if timestamps is not None else None, error, datetime.now(timezone.utc).isoformat()))
