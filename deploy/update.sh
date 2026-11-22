#!/usr/bin/env bash
# update.sh - apply a new code.tar.gz (deploy/pack.py --code-only) on the server and restart the worker.
#   scp code.tar.gz -> /tmp on the server, then:  sudo bash /srv/cosmogon/studio/deploy/update.sh
# Keeps the data, the venv, the keys (worker/.env) and the server's own agent state (studio/out: today's quota
# ledger, the agent cache), which the archive would otherwise overwrite with the PC's copy.
set -euo pipefail
ROOT=/srv/cosmogon
SRC=${SRC:-/tmp}
U=${SUDO_USER:-ubuntu}
[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
[ -f "$SRC/code.tar.gz" ] || { echo "missing $SRC/code.tar.gz"; exit 1; }
tar -xzf "$SRC/code.tar.gz" -C "$ROOT" --exclude='studio/out/*'
install -m 644 "$ROOT/studio/deploy/worker.linux.env" "$ROOT/worker.env"
sed "s/__USER__/$U/" "$ROOT/studio/deploy/cosmogon-worker.service" > /etc/systemd/system/cosmogon-worker.service
chown -R "$U:$U" "$ROOT/studio" "$ROOT/lab"
systemctl daemon-reload
# restart only if it is already serving: before the switch-over (step 5) an update must not start it
if systemctl is-active --quiet cosmogon-worker; then
  systemctl restart cosmogon-worker
  sleep 3
  systemctl --no-pager --lines=5 status cosmogon-worker || true
  echo "updated and restarted; follow with: journalctl -u cosmogon-worker -f"
else
  echo "updated (the service is not running, so it was not started)"
fi
