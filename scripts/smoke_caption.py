"""Describe one existing local video with the real model, persist and report."""
import json
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.library import Library
from services.captions import CaptionService

library = Library('data')
assets = library.list_assets(media_type='video')
if not assets:
    raise SystemExit('Import a video before running this smoke test.')
service = CaptionService(library, SimpleNamespace(lock=threading.Lock(), encoder=None))
started = time.perf_counter()
caption = service.describe(assets[0]['id'])
report = {'asset_id': assets[0]['id'], 'seconds': time.perf_counter()-started, 'caption': caption}
Path('data/caption-smoke.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True), flush=True)
