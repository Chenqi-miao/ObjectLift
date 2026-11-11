"""One batch owns one offline worker; closing it releases GPU memory."""
import json
import subprocess
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace


class CaptionSession:
    def __init__(self, root):
        self.process = None
        self.log = tempfile.TemporaryFile(dir=root)

    def __enter__(self):
        return self

    def close_worker(self):
        if self.process is not None:
            if self.process.poll() is None:
                self.process.terminate()
            self.process.wait(timeout=30)
            self.process.stdin.close()
            self.process = None

    def __exit__(self, *args):
        try:
            self.close_worker()
        finally:
            self.log.close()

    def run(self, args, **kwargs):
        if self.process is None or self.process.poll() is not None:
            self.close_worker()
            self.process = subprocess.Popen(args[:2] + ['--session'], stdin=subprocess.PIPE,
                stdout=self.log, stderr=self.log, text=True, encoding='utf-8',
                env=kwargs['env'], creationflags=kwargs.get('creationflags', 0))
        try:
            self.process.stdin.write(json.dumps(args[2:4]) + '\n')
            self.process.stdin.flush()
            deadline = time.monotonic() + kwargs['timeout']
            while not Path(args[3]).exists():
                if self.process.poll() is not None:
                    raise RuntimeError('描述进程退出，请重试该素材。')
                if time.monotonic() >= deadline:
                    raise TimeoutError('描述超时，请重试该素材。')
                time.sleep(0.05)
            return SimpleNamespace(returncode=0)
        except Exception:
            self.close_worker()
            raise
