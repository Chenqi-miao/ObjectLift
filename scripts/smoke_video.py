"""Real FFmpeg import/timestamp smoke test; does not evaluate model quality."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from services.library import Library
from services.video import run


with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    source = root / 'sample.mp4'
    run('ffmpeg', ['-nostdin', '-f', 'lavfi', '-i', 'testsrc2=size=320x240:rate=25',
                   '-t', '12', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', source])
    library = Library(root / 'data')
    result = library.import_files([source, source])
    assert [r['status'] for r in result] == ['imported', 'duplicate'], result
    asset = library.get_asset(result[0]['asset_id'])
    times = [item['timestamp_ms'] for item in asset['items']]
    assert times == [0, 5000, 10000], times
    assert asset['duration_ms'] == 12000, asset['duration_ms']
    assert all((library.root / item['preview_path']).is_file() for item in asset['items'])
    print('PASS: real H.264 import, duplicate detection, 3 frames at', times)
