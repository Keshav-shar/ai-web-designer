#!/usr/bin/env bash
# bootstrap.sh - set up the Cosmogon engine on a fresh Ubuntu 24.04 (arm64 or x86_64) server. Safe to re-run.
#
#   scp code.tar.gz data.tar worker.env  ->  /tmp on the server   (worker.env = your D:\serpman-studio\worker\.env)
#   tar -xzf /tmp/code.tar.gz -C /tmp studio/deploy/bootstrap.sh && sudo bash /tmp/studio/deploy/bootstrap.sh
#
# Layout: /srv/cosmogon/{studio (worker, contracts, deploy, out), lab, data/serpman_data, cache, tmp, venv, worker.env}
# Leaves the service installed but NOT started: start it once the checks pass (deploy/README.md, step 5).
set -euo pipefail

ROOT=/srv/cosmogon
SRC=${SRC:-/tmp}
U=${SUDO_USER:-ubuntu}
TORCH="torch==2.10.0 torchvision==0.25.0"
say() { printf '\n\033[1;32m== %s\033[0m\n' "$*"; }

[ "$(id -u)" -eq 0 ] || { echo "run with sudo"; exit 1; }
for f in code.tar.gz data.tar; do [ -f "$SRC/$f" ] || { echo "missing $SRC/$f"; exit 1; }; done

say "1/8 swap (4 GB): the engine peaks at ~1.6 GB and Chromium adds ~0.4 GB on a 2 GB machine"
if ! swapon --show=NAME --noheadings | grep -qx /swapfile; then
  fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile >/dev/null && swapon /swapfile
  grep -q '^/swapfile ' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi
echo 'vm.swappiness=20' > /etc/sysctl.d/90-cosmogon.conf && sysctl -q --system
free -h

say "2/8 system packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq --no-install-recommends ca-certificates curl tar time >/dev/null

say "3/8 unpack code and data into $ROOT"
mkdir -p "$ROOT"/{data,cache,tmp}
tar -xzf "$SRC/code.tar.gz" -C "$ROOT"
if [ ! -f "$ROOT/data/.unpacked" ] || [ "$SRC/data.tar" -nt "$ROOT/data/.unpacked" ]; then
  tar -xf "$SRC/data.tar" -C "$ROOT/data" && touch "$ROOT/data/.unpacked"
fi
mkdir -p "$ROOT/studio/out/_agents" "$ROOT/studio/out/_landing"
du -sh "$ROOT/data/serpman_data/ui_drafts/p1/context-cream" "$ROOT/data/serpman_data/ui_drafts/p1/_context" \
       "$ROOT/data/serpman_data/fonts" 2>/dev/null || true

say "4/8 keys: worker/.env (mode 600, owner $U)"
if [ -f "$SRC/worker.env" ]; then
  install -m 600 -o "$U" -g "$U" "$SRC/worker.env" "$ROOT/studio/worker/.env"
  shred -u "$SRC/worker.env" 2>/dev/null || rm -f "$SRC/worker.env"
fi
[ -f "$ROOT/studio/worker/.env" ] || echo "WARNING: no $ROOT/studio/worker/.env yet (copy your worker/.env to $SRC/worker.env and re-run)"
install -m 644 "$ROOT/studio/deploy/worker.linux.env" "$ROOT/worker.env"
chown -R "$U:$U" "$ROOT"

say "5/8 Python 3.13 (uv) + the pinned packages"
UV=/home/$U/.local/bin/uv
[ -x "$UV" ] || sudo -u "$U" -H bash -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' >/dev/null
[ -x "$ROOT/venv/bin/python" ] || sudo -u "$U" -H "$UV" venv -q --python 3.13 "$ROOT/venv"
# torch first, CPU-only wheels (no CUDA download); fall back to PyPI if this exact build isn't on the CPU index
sudo -u "$U" -H "$UV" pip install -q --python "$ROOT/venv/bin/python" --index-url https://download.pytorch.org/whl/cpu $TORCH \
  || sudo -u "$U" -H "$UV" pip install -q --python "$ROOT/venv/bin/python" $TORCH
sudo -u "$U" -H "$UV" pip install -q --python "$ROOT/venv/bin/python" -r "$ROOT/studio/deploy/requirements-linux.txt"
"$ROOT/venv/bin/python" -c "import torch, open_clip, cv2, skimage, playwright; print('torch', torch.__version__, '| cuda', torch.cuda.is_available())"

say "6/8 Chromium for the mockup screenshot and the page checks (Playwright, with its system libraries)"
PLAYWRIGHT_BROWSERS_PATH="$ROOT/cache/ms-playwright" "$ROOT/venv/bin/python" -m playwright install --with-deps chromium >/dev/null
chown -R "$U:$U" "$ROOT/cache"

say "7/8 CLIP ViT-B-32 (laion2b_s34b_b79k) into $ROOT/cache/huggingface: the same public checkpoint as the PC"
sudo -u "$U" -H env HF_HOME="$ROOT/cache/huggingface" OMP_NUM_THREADS=2 "$ROOT/venv/bin/python" -c \
  "import open_clip; open_clip.create_model_and_transforms('ViT-B-32', pretrained='laion2b_s34b_b79k', cache_dir='$ROOT/cache/huggingface'); print('CLIP ready')"

say "8/8 the systemd service (installed, not started)"
sed "s/__USER__/$U/" "$ROOT/studio/deploy/cosmogon-worker.service" > /etc/systemd/system/cosmogon-worker.service
systemctl daemon-reload
chmod +x "$ROOT/studio/deploy/"*.sh

say "done. Next: bash $ROOT/studio/deploy/check.sh   (then: sudo systemctl enable --now cosmogon-worker)"
