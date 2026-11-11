import json,time,threading,hashlib,argparse,sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
parser=argparse.ArgumentParser(); parser.add_argument("--mode",choices=["single","batch"],required=True); args=parser.parse_args()
from pathlib import Path
from types import SimpleNamespace
from services.library import Library
from services.captions import CaptionService
root=Path('data/optimization-caption')/args.mode/time.strftime('%Y%m%d-%H%M%S'); root.mkdir(parents=True,exist_ok=True)
files=sorted(Path('data/test-media/coco128/images/train2017').glob('*.jpg'))[:3]
report={'files':[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],'runs':[]}
for n in range(3):
 lib=Library(root/f'before-{n}'); ids=[r['asset_id'] for r in lib.import_files(files)]
 svc=CaptionService(lib,SimpleNamespace(lock=threading.Lock(),encoder=None)); start=time.perf_counter(); results=[]
 if args.mode == 'batch':
  results=list(svc.describe_many(ids))
 else:
  for aid in ids:
   try: results.append({'id':aid,'output':svc.describe(aid)})
   except Exception as e: results.append({'id':aid,'error':str(e)})
 report['runs'].append({'seconds':time.perf_counter()-start,'results':results}); (root/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(n,report['runs'][-1]['seconds'],flush=True)
