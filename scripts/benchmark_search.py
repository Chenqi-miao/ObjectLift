"""Measure local search stages without importing or reindexing user assets."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.embeddings import JinaEncoder
from services.indexing import IndexService
from services.library import Library


library = Library(os.getenv('OBJECTLIFT_DATA', 'data'))
# Avoid worker startup recovery while the user's application may be running.
library.recover_interrupted = lambda: None
service = IndexService(library, JinaEncoder())
reports = []
for query in ['街道上的汽车', '树林中的小路', '树林中的小路']:
    hits = service.search(query)
    report = {'query': query, 'hits': len(hits), **service.last_search_stats}
    reports.append(report)
    print(json.dumps(report, ensure_ascii=True), flush=True)
output = Path('data/search-benchmark.json')
output.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
