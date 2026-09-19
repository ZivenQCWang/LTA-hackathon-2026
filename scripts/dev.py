"""Start both local services and shut them down together with Ctrl+C."""
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
node=shutil.which('node')
vite=ROOT/'node_modules/vite/bin/vite.js'
if not node or not vite.exists():
    raise SystemExit('Install Node.js and run npm install in the project folder first.')
children=[]
try:
    children.append(subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port','8000'],cwd=ROOT))
    children.append(subprocess.Popen([node,str(vite),'--host','127.0.0.1','--port','5173','--strictPort'],cwd=ROOT))
    print('PLiZ: http://127.0.0.1:5173 — Ctrl+C stops both services.',flush=True)
    while all(p.poll() is None for p in children): time.sleep(.5)
except KeyboardInterrupt:
    pass
finally:
    for process in children:
        if process.poll() is None: process.terminate()
    for process in children:
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill()
