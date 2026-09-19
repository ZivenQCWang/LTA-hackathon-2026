#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
  echo 'Run this reviewed installer with sudo.' >&2
  exit 64
fi
release_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
if [[ ! -f /etc/pliz.env ]]; then
  install -m 600 -o root -g root "$release_dir/deploy/private/production.env" /etc/pliz.env
fi
bash "$release_dir/deploy/install-server.sh" "$release_dir"
healthy=false
for attempt in {1..30}; do
  if curl --silent --fail http://127.0.0.1:8016/api/health >/dev/null; then
    healthy=true
    break
  fi
  sleep 1
done
if [[ $healthy != true ]]; then
  echo 'PLiZ did not become healthy; tunnel configuration was left unchanged.' >&2
  exit 1
fi
python3 "$release_dir/deploy/configure-tunnel.py"
systemctl is-active pliz.service
echo 'PLiZ is running. Point the pliz DNS record to the existing tunnel, then verify HTTPS.'
