"""Persistent v2 library. Imported originals never replace the user's files."""
import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from PIL import Image

from services.image_io import load_image
from services.video import extract_video


class Library:
    def __init__(self, root: str | Path = 'data'):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            version = db.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1):
                raise ValueError('不支持的素材库版本。')
            db.execute('PRAGMA journal_mode=WAL')
            db.executescript('''
                CREATE TABLE IF NOT EXISTS assets (
                    id TEXT PRIMARY KEY, sha256 TEXT UNIQUE NOT NULL,
                    original_name TEXT NOT NULL, stored_path TEXT NOT NULL,
                    media_type TEXT NOT NULL, size_bytes INTEGER NOT NULL,
                    width INTEGER, height INTEGER, duration_ms INTEGER,
                    status TEXT NOT NULL, error_code TEXT, error_message TEXT,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS visual_items (
                    id TEXT PRIMARY KEY, asset_id TEXT NOT NULL REFERENCES assets(id),
                    sample_index INTEGER NOT NULL, timestamp_ms INTEGER,
                    preview_path TEXT NOT NULL, caption TEXT,
                    caption_status TEXT NOT NULL, embedding_status TEXT NOT NULL,
                    embedding BLOB, embedding_dim INTEGER,
                    embedding_model TEXT, embedding_revision TEXT,
                    caption_model TEXT, caption_revision TEXT,
                    preprocess_version TEXT NOT NULL, error_message TEXT,
                    UNIQUE(asset_id, sample_index)
                );
                CREATE TABLE IF NOT EXISTS tags (
                    visual_item_id TEXT NOT NULL REFERENCES visual_items(id),
                    name TEXT NOT NULL, source TEXT NOT NULL DEFAULT 'auto',
                    PRIMARY KEY(visual_item_id, name)
                );
                CREATE INDEX IF NOT EXISTS asset_filters ON assets(media_type,status);
                CREATE INDEX IF NOT EXISTS item_asset ON visual_items(asset_id);
                CREATE INDEX IF NOT EXISTS tag_name ON tags(name);
                PRAGMA user_version=1;
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.root / 'library.sqlite3', timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def list_assets(self, media_type=None, keyword='', status=None):
        with self.connection() as db:
            return [dict(row) for row in db.execute(
                'SELECT * FROM assets WHERE (? IS NULL OR media_type=?) '
                "AND (?='' OR instr(lower(original_name), lower(?))>0) "
                'AND (? IS NULL OR status=?) ORDER BY created_at DESC, id',
                (media_type, media_type, keyword.strip(), keyword.strip(), status, status))]

    def statistics(self):
        with self.connection() as db:
            counts = dict(db.execute('SELECT status, count(*) FROM assets GROUP BY status'))
            searchable = db.execute("SELECT count(DISTINCT asset_id) FROM visual_items WHERE embedding_status='ready'").fetchone()[0]
        return {'total': sum(counts.values()), 'searchable': searchable, **counts}

    def get_asset(self, asset_id):
        with self.connection() as db:
            row = db.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
            if row is None:
                raise KeyError(asset_id)
            result = dict(row)
            result['items'] = [dict(item) for item in db.execute(
                'SELECT * FROM visual_items WHERE asset_id=? ORDER BY sample_index',
                (asset_id,))]
            return result

    def import_files(self, paths):
        results = []
        for path in paths:
            try:
                results.append(self.import_video(path) if Path(path).suffix.lower() == '.mp4' else self.import_image(path))
            except (OSError, ValueError) as exc:
                results.append({'filename': Path(path).name, 'status': 'failed',
                                'error': str(exc)})
        return results

    def import_video(self, path):
        source = Path(path)
        asset_id = uuid4().hex
        with TemporaryDirectory(prefix='video-', dir=self.root) as temporary:
            staged = Path(temporary) / 'original.mp4'
            digest, size = hashlib.sha256(), 0
            with source.open('rb') as src, staged.open('wb') as dst:
                while chunk := src.read(1024 * 1024):
                    size += len(chunk)
                    if size > 300 * 1024 * 1024:
                        raise ValueError('视频不能超过 300MB。')
                    digest.update(chunk)
                    dst.write(chunk)
            with self.connection() as db:
                existing = db.execute('SELECT id FROM assets WHERE sha256=?', (digest.hexdigest(),)).fetchone()
            if existing:
                return {'filename': source.name, 'status': 'duplicate', 'asset_id': existing['id']}
            width, height, duration, frames = extract_video(staged, Path(temporary) / 'frames')
            original = Path('originals') / asset_id / 'original.mp4'
            previews = Path('previews') / asset_id
            now = datetime.now(timezone.utc).isoformat()
            with self.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT id FROM assets WHERE sha256=?', (digest.hexdigest(),)).fetchone()
                if existing:
                    return {'filename': source.name, 'status': 'duplicate', 'asset_id': existing['id']}
                (self.root / original).parent.mkdir(parents=True)
                (self.root / previews).parent.mkdir(parents=True, exist_ok=True)
                staged.replace(self.root / original)
                (Path(temporary) / 'frames').replace(self.root / previews)
                db.execute('INSERT INTO assets (id,sha256,original_name,stored_path,media_type,size_bytes,width,height,duration_ms,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                           (asset_id, digest.hexdigest(), source.name, original.as_posix(), 'video', size, width, height, duration, 'pending', now, now))
                for number, (frame, timestamp) in enumerate(frames):
                    db.execute('INSERT INTO visual_items (id,asset_id,sample_index,timestamp_ms,preview_path,caption_status,embedding_status,preprocess_version) VALUES (?,?,?,?,?,?,?,?)',
                               (uuid4().hex, asset_id, number, timestamp, (previews / frame.name).as_posix(), 'pending', 'pending', 'video-5s-v1'))
        return {'filename': source.name, 'status': 'imported', 'asset_id': asset_id}

    def import_image(self, path):
        source = Path(path)
        if source.suffix.lower() not in {'.jpg', '.jpeg', '.png'}:
            raise ValueError('导入支持 JPG/JPEG/PNG 和 H.264 MP4。')
        asset_id = uuid4().hex
        with TemporaryDirectory(prefix='import-', dir=self.root) as temporary:
            staged = Path(temporary) / 'original'
            digest, size = hashlib.sha256(), 0
            with source.open('rb') as src, staged.open('wb') as dst:
                while chunk := src.read(1024 * 1024):
                    size += len(chunk)
                    if size > 20 * 1024 * 1024:
                        raise ValueError('图片不能超过 20MB。')
                    digest.update(chunk)
                    dst.write(chunk)
            image = load_image(staged, max_side=40_000_000)
            width, height = image.size
            with Image.open(staged) as raw:
                extension = '.jpg' if raw.format == 'JPEG' else '.png'
            original = Path('originals') / asset_id / ('original' + extension)
            preview = Path('previews') / asset_id / 'preview.png'
            image.thumbnail((512, 512), Image.Resampling.LANCZOS)
            image.save(Path(temporary) / 'preview.png')
            now = datetime.now(timezone.utc).isoformat()
            with self.connection() as db:
                db.execute('BEGIN IMMEDIATE')
                existing = db.execute('SELECT id FROM assets WHERE sha256=?',
                                      (digest.hexdigest(),)).fetchone()
                if existing:
                    return {'filename': source.name, 'status': 'duplicate',
                            'asset_id': existing['id']}
                for relative in (original, preview):
                    (self.root / relative).parent.mkdir(parents=True, exist_ok=True)
                staged.replace(self.root / original)
                (Path(temporary) / 'preview.png').replace(self.root / preview)
                db.execute('''INSERT INTO assets
                    (id,sha256,original_name,stored_path,media_type,size_bytes,
                     width,height,status,created_at,updated_at)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)''',
                    (asset_id, digest.hexdigest(), source.name, original.as_posix(),
                     'image', size, width, height, 'pending', now, now))
                db.execute('''INSERT INTO visual_items
                    (id,asset_id,sample_index,preview_path,caption_status,
                     embedding_status,preprocess_version) VALUES (?,?,?,?,?,?,?)''',
                    (uuid4().hex, asset_id, 0, preview.as_posix(),
                     'pending', 'pending', 'image-exif-v1'))
        return {'filename': source.name, 'status': 'imported', 'asset_id': asset_id}

    def recover_interrupted(self):
        """Call once at worker startup, never while another worker is indexing."""
        with self.connection() as db:
            for column in ('caption_status', 'embedding_status'):
                db.execute(f"UPDATE visual_items SET {column}='pending' "
                           f"WHERE {column}='processing'")
            db.execute("UPDATE assets SET status='pending', updated_at=? "
                       "WHERE status='processing'",
                       (datetime.now(timezone.utc).isoformat(),))
