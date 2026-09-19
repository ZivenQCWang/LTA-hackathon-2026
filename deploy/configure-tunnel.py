"""Add only PLiZ to the existing locally managed 4bytedigi tunnel."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time

if os.geteuid() != 0 or socket.gethostname() != '4bytedigi':
    raise SystemExit('Run as root on 4bytedigi after verifying the PLiZ origin.')
config = Path('/etc/cloudflared/config.yml')
original = config.read_text()
stat = config.stat()
hostname = 'pliz.4bytedigi.com'
route = f'  - hostname: {hostname}\n    service: http://127.0.0.1:8016\n'
if route in original:
    print('PLiZ tunnel route already configured.')
    raise SystemExit(0)
if hostname in original:
    raise SystemExit('A different PLiZ route exists. Inspect it before changing it.')
marker = '  - service: http_status:404'
if original.count(marker) != 1:
    raise SystemExit('Expected one fallback route; no configuration was changed.')
backup = config.with_name('config.yml.before-pliz-' + time.strftime('%Y%m%dT%H%M%S'))
shutil.copy2(config, backup)
os.chown(backup, stat.st_uid, stat.st_gid)
staged = config.with_name('config.yml.pliz-staged')
shutil.copy2(config, staged)
staged.write_text(original.replace(marker, route + marker))
os.chown(staged, stat.st_uid, stat.st_gid)
subprocess.run(['runuser', '-u', 'cloudconnector', '--', '/usr/bin/cloudflared', '--config', str(staged), 'tunnel', 'ingress', 'validate'], check=True)
os.replace(staged, config)
try:
    subprocess.run(['systemctl', 'restart', 'dbstudios-tunnel'], check=True)
    subprocess.run(['systemctl', 'is-active', '--quiet', 'dbstudios-tunnel'], check=True)
except Exception:
    shutil.copy2(backup, config)
    os.chown(config, stat.st_uid, stat.st_gid)
    subprocess.run(['systemctl', 'restart', 'dbstudios-tunnel'], check=False)
    raise
print('PLiZ tunnel route enabled. Other routes preserved. Backup:', backup)
