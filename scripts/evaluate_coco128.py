"""COCO128 category-label retrieval baseline; not general scene quality."""
import json,time,math,hashlib,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from services.library import Library
from services.indexing import IndexService
from services.embeddings import JinaEncoder
root=Path('data/test-media/coco128'); images=sorted((root/'images/train2017').glob('*.jpg'))
assert len(images)==128
missing_labels=[p.name for p in images if not (root/'labels/train2017'/f'{p.stem}.txt').exists()]
images=[p for p in images if p.name not in missing_labels]
labels={p.name:{int(line.split()[0]) for line in (root/'labels/train2017'/f'{p.stem}.txt').read_text().splitlines() if line.strip()} for p in images}
queries=list(enumerate(['人','自行车','汽车','摩托车','飞机','公交车','火车','卡车','船']))+[(14,'鸟'),(15,'猫'),(16,'狗'),(17,'马'),(18,'羊'),(19,'牛'),(20,'大象'),(21,'熊'),(22,'斑马'),(23,'长颈鹿'),(24,'背包')]
plan=[{'category_id':i,'query':f'有{name}的图片','relevant':[p for p,c in labels.items() if i in c]} for i,name in queries]
out=Path('docs/evidence/qa-2026-11-12');(out/'retrieval-plan.json').write_text(json.dumps({'queries':plan,'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in images}},ensure_ascii=False,indent=2),encoding='utf-8')
lib=Library('data/qa-retrieval-coco128');lib.import_files(images);encoder=JinaEncoder();index=IndexService(lib,encoder)
for update in index.index_pending():print(update,flush=True)
index.warmup();results=[]
for query in plan:
 started=time.perf_counter();hits=index.search(query['query'],limit=5);elapsed=time.perf_counter()-started
 relevant=set(query['relevant']);names=[h['original_name'] for h in hits]
 results.append({**query,'top5':names,'scores':[h['similarity'] for h in hits],'seconds':elapsed,'hit5':bool(relevant.intersection(names)) if relevant else None,'precision5':len(relevant.intersection(names))/5 if relevant else None})
positive=[r for r in results if r['relevant']]
report={'scope':'COCO128 subset with label files present; no human scene review; not 1000-unit acceptance','model':encoder.model_id,'revision':encoder.revision,'indexed_images':len(images),'excluded_missing_labels':missing_labels,'positive_queries':len(positive),'label_empty_queries':len(results)-len(positive),'hit5':sum(r['hit5'] for r in positive)/len(positive),'precision5':sum(r['precision5'] for r in positive)/len(positive),'results':results}
(out/'retrieval-results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');encoder.unload();print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False),flush=True)
