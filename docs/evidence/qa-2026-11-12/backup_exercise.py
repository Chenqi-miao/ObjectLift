"""Isolated stopped-writer backup/restore exercise; never reads the user library."""
import hashlib,json,shutil,sqlite3,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
from PIL import Image
from services.library import Library
from services.indexing import IndexService
from types import SimpleNamespace
with tempfile.TemporaryDirectory() as tmp:
 root=Path(tmp); lib=Library(root/'source'); files=[]
 for color in ('red','blue'):
  path=root/f'{color}.png'; Image.new('RGB',(16,16),color).save(path);files.append(path)
 ids=[x['asset_id'] for x in lib.import_files(files)]
 encoder=SimpleNamespace(model_id='backup-test-only',revision='v1',image=lambda p:[1,0],text=lambda q:[1,0])
 list(IndexService(lib,encoder).index_pending());lib.trash_asset(ids[1])
 restored=root/'restored';restored.mkdir()
 with sqlite3.connect(lib.root/'library.sqlite3') as source,sqlite3.connect(restored/'library.sqlite3') as dest:
  source.backup(dest)
 for folder in ('originals','previews'):shutil.copytree(lib.root/folder,restored/folder)
 def hashes(base):return {str(p.relative_to(base)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ('originals','previews') for p in (base/folder).rglob('*') if p.is_file()}
 assert hashes(lib.root)==hashes(restored)
 counts={}
 with sqlite3.connect(lib.root/'library.sqlite3') as a,sqlite3.connect(restored/'library.sqlite3') as b:
  for table in ('assets','visual_items','tags','video_descriptions','asset_trash'):
   left=a.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall();right=b.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall();assert left==right,table;counts[table]=len(left)
  assert b.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
 source.close();dest.close();a.close();b.close()
 loaded=Library(restored);assert len(IndexService(loaded,encoder).search('test'))==1
 loaded.restore_asset(ids[1]);assert len(IndexService(loaded,encoder).search('test'))==2
 print(json.dumps({'status':'PASS','scope':'isolated 2-image stopped-writer backup, mock vectors; not production-scale restore','tables':counts,'media_hashes_equal':True,'integrity_check':'ok','search_before_restore':1,'search_after_restore':2},indent=2))
