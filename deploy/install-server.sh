#!/usr/bin/env bash
# Install a reviewed release; does not modify DNS or existing tunnel routes.
set -euo pipefail
umask 022
if [[ $EUID -ne 0 || $# -ne 1 ]]; then
  echo 'Usage: sudo bash deploy/install-server.sh /absolute/staged-release-directory' >&2
  exit 64
fi
source_dir=$(realpath "$1")
for file in backend/main.py dist/index.html requirements.txt deploy/pliz.service; do
  test -f "$source_dir/$file" || { echo "Missing release file: $file" >&2; exit 1; }
done
test -f /etc/pliz.env || { echo 'Create /etc/pliz.env with production settings first.' >&2; exit 1; }
release="/opt/pliz/releases/$(date -u +%Y%m%dT%H%M%SZ)"
id pliz >/dev/null 2>&1 || useradd --system --home-dir /var/lib/pliz --shell /usr/sbin/nologin pliz
install -d -m 755 /opt/pliz /opt/pliz/releases "$release"
install -d -o pliz -g pliz -m 700 /var/lib/pliz
cp -a "$source_dir/backend" "$source_dir/data" "$source_dir/dist" "$release/"
install -m 644 "$source_dir/requirements.txt" "$release/requirements.txt"
install -d -m 755 "$release/storage"
if ! python3 -c 'import ensurepip' >/dev/null 2>&1; then
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
fi
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" install -r "$release/requirements.txt"
chown -R root:root "$release"
chmod -R go-w "$release"
chmod 600 /etc/pliz.env
if [[ -e /opt/pliz/current && ! -L /opt/pliz/current ]]; then
  echo '/opt/pliz/current is not a symlink; stopping without replacing it.' >&2
  exit 1
fi
ln -sfn "$release" /opt/pliz/current
install -m 644 "$source_dir/deploy/pliz.service" /etc/systemd/system/pliz.service
systemctl daemon-reload
systemctl enable --now pliz.service
systemctl restart pliz.service
echo "Installed $release. Verify /api/health before changing public routing."
