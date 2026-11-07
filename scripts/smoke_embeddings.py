"""Real inference smoke check, never uses a fake encoder."""
import json
import sys
import time
import faulthandler
faulthandler.dump_traceback_later(45, repeat=True)
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import torch
from PIL import Image
from services.embeddings import JinaEncoder
from services.indexing import IndexService
from services.library import Library

root = Path('data/model-smoke') / time.strftime('%Y%m%d-%H%M%S')
root.mkdir(parents=True, exist_ok=True)
for color in ('red', 'blue', 'green'):
    Image.new('RGB', (512, 512), color).save(root / f'{color}.png')
lib = Library(root / 'library')
lib.import_files([root / f'{c}.png' for c in ('red', 'blue', 'green')])
encoder = JinaEncoder()
service = IndexService(lib, encoder)
started = time.perf_counter()
for status in service.index_pending():
    print(status, flush=True)
hits = service.search('红色的图片')
report = {'torch': torch.__version__, 'cuda': torch.cuda.is_available(), 'seconds': time.perf_counter()-started, 'hits': hits, 'peak_gpu_mb': torch.cuda.max_memory_allocated()/1024**2 if torch.cuda.is_available() else 0}
started = time.perf_counter()
service.search('蓝色的图片')
report['warm_query_seconds'] = time.perf_counter() - started
report['device'] = torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'cpu'
report['peak_reserved_mb'] = torch.cuda.max_memory_reserved()/1024**2 if torch.cuda.is_available() else 0
faulthandler.cancel_dump_traceback_later()
(root / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=True), flush=True)
if len(hits) != 3 or hits[0]['original_name'] != 'red.png':
    raise SystemExit('Real model smoke check failed')
