"""Serial indexing and compatible-vector retrieval; inference never holds a DB lock."""
import threading
from collections import OrderedDict
from time import perf_counter
from datetime import datetime, timezone

import numpy as np


def normalize(value):
    vector = np.asarray(value, dtype='<f4')
    if vector.ndim != 1 or not vector.size or not np.isfinite(vector).all():
        raise ValueError('模型返回无效向量。')
    norm = np.linalg.norm(vector)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError('模型返回零向量或溢出向量。')
    return (vector / norm).astype('<f4')


class IndexService:
    def __init__(self, library, encoder):
        self.library, self.encoder = library, encoder
        self.lock = threading.Lock()
        self.query_cache = OrderedDict()
        self.last_search_stats = {}
        library.recover_interrupted()

    def warmup(self):
        if not self.lock.acquire(blocking=False):
            raise ValueError('索引或查询正在运行，请稍后重试。')
        try:
            started = perf_counter()
            normalize(self.encoder.text('图片'))
            return perf_counter() - started
        finally:
            self.lock.release()

    def index_pending(self):
        if not self.lock.acquire(blocking=False):
            raise ValueError('索引或查询正在运行，请稍后重试。')
        try:
            with self.library.connection() as db:
                rows = db.execute("SELECT v.*, a.stored_path FROM visual_items v JOIN assets a ON a.id=v.asset_id WHERE embedding_status != 'ready' OR embedding_model != ? OR embedding_revision != ?", (self.encoder.model_id, self.encoder.revision)).fetchall()
            yield f'准备索引 {len(rows)} 个画面'
            for number, row in enumerate(rows, 1):
                with self.library.connection() as db:
                    db.execute("UPDATE visual_items SET embedding_status='processing', error_message=NULL WHERE id=?", (row['id'],))
                    db.execute("UPDATE assets SET status='processing' WHERE id=?", (row['asset_id'],))
                try:
                    vector = normalize(self.encoder.image(self.library.root / (row['preview_path'] if row['timestamp_ms'] is not None else row['stored_path'])))
                    with self.library.connection() as db:
                        db.execute("UPDATE visual_items SET embedding=?, embedding_dim=?, embedding_model=?, embedding_revision=?, embedding_status='ready' WHERE id=?", (vector.tobytes(), len(vector), self.encoder.model_id, self.encoder.revision, row['id']))
                    message = '向量就绪'
                except Exception as exc:
                    message = str(exc)
                    with self.library.connection() as db:
                        db.execute("UPDATE visual_items SET embedding_status='failed', error_message=? WHERE id=?", (message, row['id']))
                with self.library.connection() as db:
                    states = db.execute('SELECT caption_status, embedding_status FROM visual_items WHERE asset_id=?', (row['asset_id'],)).fetchall()
                    status = 'ready' if all(s[0] == s[1] == 'ready' for s in states) else ('partial' if any(s[1] == 'ready' for s in states) else 'failed')
                    db.execute('UPDATE assets SET status=?, updated_at=? WHERE id=?', (status, datetime.now(timezone.utc).isoformat(), row['asset_id']))
                yield f'{number}/{len(rows)} · {message}'
        finally:
            self.lock.release()

    def search(self, query, limit=10, media_type=None):
        started = perf_counter()
        if not query.strip():
            return []
        if not self.lock.acquire(blocking=False):
            raise ValueError('索引或查询正在运行，请稍后重试。')
        try:
            with self.library.connection() as db:
                rows = db.execute("SELECT v.*, a.original_name, a.media_type FROM visual_items v JOIN assets a ON a.id=v.asset_id WHERE embedding_status='ready' AND embedding_model=? AND embedding_revision=? AND (? IS NULL OR a.media_type=?)", (self.encoder.model_id, self.encoder.revision, media_type, media_type)).fetchall()
            if not rows:
                self.last_search_stats = {'total_seconds': perf_counter() - started, 'cache_hit': False}
                return []
            loaded = perf_counter()
            key = (self.encoder.model_id, self.encoder.revision, query.strip())
            cached = key in self.query_cache
            if cached:
                query_vector = self.query_cache.pop(key)
            else:
                query_vector = normalize(self.encoder.text(query.strip()))
            self.query_cache[key] = query_vector
            if len(self.query_cache) > 64:
                self.query_cache.popitem(last=False)
            encoded = perf_counter()
            hits = []
            vectors = []
            for row in rows:
                if row['embedding_dim'] != len(query_vector):
                    continue
                vector = normalize(np.frombuffer(row['embedding'], dtype='<f4'))
                hit = {key: row[key] for key in ('asset_id', 'preview_path', 'original_name', 'caption', 'timestamp_ms', 'media_type')}
                hit['visual_item_id'] = row['id']
                hits.append(hit)
                vectors.append(vector)
            if vectors:
                scores = np.stack(vectors) @ query_vector
                for hit, score in zip(hits, scores):
                    hit['similarity'] = float(score)
            selected = []
            for hit in sorted(hits, key=lambda hit: hit['similarity'], reverse=True):
                if hit['timestamp_ms'] is not None and any(
                    other['asset_id'] == hit['asset_id'] and
                    abs(other['timestamp_ms'] - hit['timestamp_ms']) < 10000 for other in selected):
                    continue
                selected.append(hit)
            self.last_search_stats = {
                'total_seconds': perf_counter() - started,
                'read_seconds': loaded - started,
                'encode_seconds': encoded - loaded,
                'rank_seconds': perf_counter() - encoded,
                'cache_hit': cached,
            }
            return selected[:limit]
        finally:
            self.lock.release()
