#!/usr/bin/env bash
# Activate an existing PLiZ installation with DBStudios reports; preserve other services.
set -euo pipefail
umask 077
if [[ $EUID -ne 0 || $# -ne 2 ]]; then
  echo 'Usage: sudo bash deploy/enable-public-reports.sh /absolute/staged-release /absolute/private-db.env' >&2
  exit 64
fi
source_dir=$(realpath "$1")
config_patch=$(realpath "$2")
test -f "$source_dir/deploy/install-server.sh"
test -f "$config_patch"
test -f /etc/pliz.env
test -L /opt/pliz/current
previous=$(readlink -f /opt/pliz/current)
stamp=$(date -u +%Y%m%dT%H%M%SZ)
backup="/etc/pliz.env.before-public-reports-$stamp"
service_backup="/etc/systemd/system/pliz.service.before-public-reports-$stamp"
cp -p /etc/pliz.env "$backup"
cp -p /etc/systemd/system/pliz.service "$service_backup"
rollback() {
  local status=$?
  trap - ERR
  cp -p "$backup" /etc/pliz.env
  cp -p "$service_backup" /etc/systemd/system/pliz.service
  ln -sfn "$previous" /opt/pliz/current
  systemctl daemon-reload
  systemctl restart pliz.service
  echo 'Activation failed; restored the previous release and environment.' >&2
  exit "$status"
}
trap rollback ERR

python3 - "$config_patch" "$source_dir" <<'PY'
import os
from pathlib import Path
import re
import secrets
import shlex
import sys

patch_path, staged = Path(sys.argv[1]), Path(sys.argv[2])
env_path = Path('/etc/pliz.env')
original = env_path.read_text()
def parse(text):
    result = {}
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        key, separator, value = line.partition('=')
        if separator:
            parsed = shlex.split(value, comments=True)
            result[key.strip()] = parsed[0] if parsed else ''
    return result

patch = parse(patch_path.read_text())
if set(patch) != {'DBSTUDIOS_API_URL', 'DBSTUDIOS_API_KEY'}:
    raise SystemExit('The private patch must contain exactly the two DBStudios settings.')
if not re.fullmatch(r'https://dbstudios\.pyiesone\.dev/api/v1/projects/[a-zA-Z0-9]+', patch['DBSTUDIOS_API_URL']):
    raise SystemExit('Unexpected DBStudios project API URL.')
if not re.fullmatch(r'[a-zA-Z0-9_.-]{20,}', patch['DBSTUDIOS_API_KEY']):
    raise SystemExit('Unexpected project key format.')
existing = parse(original)
if not existing.get('PLIZ_AUTH_USERNAME') or len(existing.get('PLIZ_AUTH_PASSWORD', '')) < 16:
    patch.update(PLIZ_AUTH_USERNAME='operator', PLIZ_AUTH_PASSWORD=secrets.token_urlsafe(32))
    login_path = staged / 'operator-login.txt'
    login_path.write_text('PLiZ public report inbox\nUsername: operator\nPassword: ' + patch['PLIZ_AUTH_PASSWORD'] + '\n')
    os.chmod(login_path, 0o600)
    owner = staged.stat()
    os.chown(login_path, owner.st_uid, owner.st_gid)
    print('Created operator credentials in the private staged directory: operator-login.txt')
else:
    print('Preserved existing operator credentials.')
kept = [line for line in original.splitlines() if line.partition('=')[0].strip() not in patch]
env_path.write_text('\n'.join(kept) + '\n' + ''.join(f'{key}={value}\n' for key, value in patch.items()))
os.chmod(env_path, 0o600)
PY

bash "$source_dir/deploy/install-server.sh" "$source_dir"
/opt/pliz/current/.venv/bin/python - <<'PY'
import base64
import time
import urllib.request
from dotenv import dotenv_values

env = dotenv_values('/etc/pliz.env')
for attempt in range(30):
    try:
        with urllib.request.urlopen('http://127.0.0.1:8016/api/health', timeout=5) as response:
            assert response.status == 200
        break
    except Exception:
        if attempt == 29:
            raise SystemExit('PLiZ health check failed.')
        time.sleep(1)
login = base64.b64encode((env['PLIZ_AUTH_USERNAME'] + ':' + env['PLIZ_AUTH_PASSWORD']).encode()).decode()
request = urllib.request.Request('http://127.0.0.1:8016/api/operator/reports', headers={'Authorization': 'Basic ' + login})
try:
    with urllib.request.urlopen(request, timeout=45) as response:
        assert response.status == 200
except Exception:
    raise SystemExit('DBStudios inbox check failed.') from None
print('PLiZ health and authenticated DBStudios inbox checks passed.')
PY
trap - ERR
echo 'Public reports activated. Verify https://pliz.4bytedigi.com/public/ in the browser.'
