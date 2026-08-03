#!/usr/bin/env bash
set -euo pipefail

BROKER_IP="${BROKER_IP:-192.168.10.1}"
DCCS_URL="${DCCS_URL:-http://192.168.10.1:10019/v1/serviceCredentials/3e6970b39a82469484c8bf07807a777b}"
GATEWAY_ID="${GATEWAY_ID:-3000b05b06a441efae3e916e7ed84d3d}"
SUBDEVICE_ID="${SUBDEVICE_ID:-d2357b9619fd47ce965f6e2249c46044}"
INTERVAL="${INTERVAL:-20}"
LOG_FILE="${LOG_FILE:-/home/pi/uno_gateway_subdevice_sender.log}"

REPORT_TOPIC="/device/${GATEWAY_ID}/up/report"
HEARTBEAT_TOPIC="/device/${GATEWAY_ID}/up/heartbeat"

fetch_mqtt_credentials() {
  mapfile -t CREDS < <(
    python3 - "$DCCS_URL" <<'PY'
import json
import sys
import urllib.request

url = sys.argv[1]
with urllib.request.urlopen(url, timeout=8) as resp:
    data = json.loads(resp.read().decode())

mqtt = data["credential"]["protocols"]["mqtt"]
print(mqtt["username"])
print(mqtt["password"])
PY
  )

  MQTT_USERNAME="${CREDS[0]}"
  MQTT_PASSWORD="${CREDS[1]}"
}

publish_payload() {
  local topic="$1"
  local payload="$2"

  mosquitto_pub \
    -h "$BROKER_IP" \
    -p 1883 \
    -u "$MQTT_USERNAME" \
    -P "$MQTT_PASSWORD" \
    -t "$topic" \
    -m "$payload"
}

generate_temperature() {
  local sec
  sec="$(date +%S)"
  echo $((34 + 10#$sec % 6))
}

log_line() {
  local message="$1"
  printf '%s %s\n' "$(date --iso-8601=seconds)" "$message" | tee -a "$LOG_FILE"
}

main() {
  mkdir -p "$(dirname "$LOG_FILE")"
  touch "$LOG_FILE"
  log_line "sender started, broker=${BROKER_IP}, gateway=${GATEWAY_ID}, subdevice=${SUBDEVICE_ID}"

  while true; do
    fetch_mqtt_credentials

    local ts temp heartbeat_payload status_payload data_payload
    ts="$(date --iso-8601=seconds)"
    temp="$(generate_temperature)"

    heartbeat_payload="$(cat <<EOF
{"d_id":"${SUBDEVICE_ID}","ts":"${ts}"}
EOF
)"

    status_payload="$(cat <<EOF
{"d_id":"${SUBDEVICE_ID}","services":{"#SYS":{"properties":{"deviceStatus":{"value":"online","dataType":"string"}}}},"ts":"${ts}"}
EOF
)"

    data_payload="$(cat <<EOF
{"d_id":"${SUBDEVICE_ID}","services":{"defaultModule":{"properties":{"temperature":{"value":${temp},"dataType":"int"}}}},"ts":"${ts}"}
EOF
)"

    publish_payload "$HEARTBEAT_TOPIC" "$heartbeat_payload"
    publish_payload "$REPORT_TOPIC" "$status_payload"
    publish_payload "$REPORT_TOPIC" "$data_payload"

    log_line "published heartbeat + status + temperature=${temp}"
    sleep "$INTERVAL"
  done
}

main "$@"
