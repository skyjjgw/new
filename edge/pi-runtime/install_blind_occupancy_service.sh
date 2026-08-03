#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="blind_occupancy_edge_iotsuite.service"
PROJECT_DIR="/home/pi/blind_occupancy"
SERVICE_SRC="${PROJECT_DIR}/${SERVICE_NAME}"
SERVICE_DST="/etc/systemd/system/${SERVICE_NAME}"

if [[ ! -f "${SERVICE_SRC}" ]]; then
    echo "missing service file: ${SERVICE_SRC}" >&2
    exit 1
fi

if [[ ! -f "${PROJECT_DIR}/run_blind_occupancy_edge.sh" ]]; then
    echo "missing launcher: ${PROJECT_DIR}/run_blind_occupancy_edge.sh" >&2
    exit 1
fi

chmod +x "${PROJECT_DIR}/run_blind_occupancy_edge.sh"
chmod +x "${PROJECT_DIR}/install_blind_occupancy_service.sh"

sudo cp "${SERVICE_SRC}" "${SERVICE_DST}"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"

echo "installed: ${SERVICE_NAME}"
echo "start with: sudo systemctl start ${SERVICE_NAME}"
echo "status with: sudo systemctl status ${SERVICE_NAME} --no-pager"
echo "logs with: journalctl -u ${SERVICE_NAME} -n 100 --no-pager"
