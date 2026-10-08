#!/usr/bin/env bash
# Prepare a fresh device for the one-service Unified Edge runtime.
set -euo pipefail

EDGE_DIR="/opt/ively/edge"
AGENT_DIR="/opt/ively/agent"
CONFIG="${AGENT_DIR}/sources.json"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root: sudo bash installer/enable-unified-edge.sh" >&2
  exit 1
fi

if systemctl is-active --quiet analog-dvr-edge.service; then
  cat >&2 <<'EOF'
analog-dvr-edge is currently active. Refusing to create two publisher owners.
Validate the unified configuration first, then migrate during a maintenance window:
  sudo systemctl disable --now analog-dvr-edge.service
  sudo bash installer/enable-unified-edge.sh
EOF
  exit 2
fi

mkdir -p "${AGENT_DIR}"
if [ ! -f "${CONFIG}" ]; then
  cp "${EDGE_DIR}/configs/unified_sources.sample.json" "${CONFIG}"
  chmod 600 "${CONFIG}"
  cat <<EOF
Created ${CONFIG} from the password-free sample.

Edit its source host, published paths, and channels. Do not put credentials in it.
Run this command again after that edit to save encrypted credentials and start Unified Edge.
EOF
  exit 0
fi

PY="python3"
if [ -x "/opt/ively/venv/bin/python3" ]; then
  PY="/opt/ively/venv/bin/python3"
fi

echo "Saving encrypted DVR credentials referenced by sources.json..."
PYTHONPATH="${EDGE_DIR}" "${PY}" -m agent.unified.provision --config "${CONFIG}"

# First-time configuration is a controlled maintenance action. At normal boot
# systemd starts MediaMTX before ively-agent; no periodic restart is performed.
systemctl stop ively-agent.service 2>/dev/null || true
PYTHONPATH="${EDGE_DIR}" "${PY}" - <<'PY'
from agent.camera.mediamtx_writer import generate
from agent.camera.worker_reload import load_cams
from agent.unified.config import load_config

config = load_config()
nvr_cams = load_cams() if any(s["type"] == "nvr" for s in config["sources"]) else []
extra = [s["path"] for s in config["sources"] if s["type"] != "nvr"]
generate(nvr_cams, extra_publisher_paths=extra)
print("MediaMTX publisher paths prepared.")
PY
systemctl restart mediamtx.service
systemctl enable mediamtx.service ively-agent.service
systemctl restart ively-agent.service

echo "Unified Edge enabled. Verify: curl -s http://127.0.0.1:8080/health"
