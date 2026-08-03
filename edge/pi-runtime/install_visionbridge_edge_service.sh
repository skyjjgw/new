#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="visionbridge-edge-agent.service"
PROJECT_DIR="/opt/visionbridge/edge"
SERVICE_SRC="${PROJECT_DIR}/${SERVICE_NAME}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

if [[ ! -f "${SERVICE_SRC}" ]]; then
    echo "missing service file: ${SERVICE_SRC}" >&2
    exit 1
fi

if [[ ! -f "${PROJECT_DIR}/run_visionbridge_edge.sh" ]]; then
    echo "missing launcher: ${PROJECT_DIR}/run_visionbridge_edge.sh" >&2
    exit 1
fi

chmod +x "${PROJECT_DIR}/run_visionbridge_edge.sh"
chmod +x "${PROJECT_DIR}/install_visionbridge_edge_service.sh"

sudo cp "${SERVICE_SRC}" "${SERVICE_DST}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

echo "installed: ${SERVICE_NAME}"
echo "start with: sudo systemctl start ${SERVICE_NAME}"
echo "status with: sudo systemctl status ${SERVICE_NAME} --no-pager"
echo "logs with: journalctl -u ${SERVICE_NAME} -n 100 --no-pager"
