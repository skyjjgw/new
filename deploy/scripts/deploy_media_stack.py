"""Install and connect the VisionBridge WebRTC media stack.

Required environment variables:
  VISIONBRIDGE_SSH_PASSWORD  cloud root password
  VISIONBRIDGE_PI_PASSWORD   Raspberry Pi password

Secrets are generated on the cloud server, transferred in memory over SSH,
and written only to root-owned environment files.
"""

from __future__ import annotations

import hashlib
import os
import posixpath
from pathlib import Path

import paramiko


CLOUD_HOST = os.environ.get("VISIONBRIDGE_CLOUD_HOST", "").strip()
PI_HOST = os.environ.get("VISIONBRIDGE_EDGE_HOST", "").strip()
CLOUD_USER = os.environ.get("VISIONBRIDGE_CLOUD_USER", "root").strip()
DEVICE_ID = os.environ.get("VISIONBRIDGE_DEVICE_ID", "visionbridge-edge-01").strip()
MEDIA_VERSION = "1.18.2"
MEDIA_SHA256 = "73ed27c292e05ceb4990dcb34531f01872dfff5374b7515c45a202e0abf47706"
ROOT = Path(__file__).resolve().parents[2]
DEPLOY_ROOT = ROOT / "deploy"
EDGE_ROOT = ROOT / "edge" / "pi-runtime"


def connect(host: str, username: str, password: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, port=22, username=username, password=password, timeout=20)
    return client


def run(client: paramiko.SSHClient, script: str, timeout: int = 300) -> str:
    stdin, stdout, stderr = client.exec_command("bash -s", timeout=None)
    stdin.write(script)
    stdin.channel.shutdown_write()
    output = stdout.read().decode("utf-8", "replace")
    error = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if code:
        raise RuntimeError(f"remote command failed ({code})\n{output}\n{error}")
    return output


def upload(client: paramiko.SSHClient, local: Path, remote: str, mode: int = 0o644) -> None:
    sftp = client.open_sftp()
    try:
        sftp.put(str(local), remote)
        sftp.chmod(remote, mode)
    finally:
        sftp.close()


def read_remote(client: paramiko.SSHClient, path: str) -> str:
    sftp = client.open_sftp()
    try:
        with sftp.open(path, "r") as handle:
            return handle.read().decode("utf-8").strip()
    finally:
        sftp.close()


def write_remote(client: paramiko.SSHClient, path: str, content: str, mode: int) -> None:
    sftp = client.open_sftp()
    try:
        parent = posixpath.dirname(path)
        try:
            sftp.stat(parent)
        except FileNotFoundError:
            raise RuntimeError(f"remote directory does not exist: {parent}")
        with sftp.open(path, "w") as handle:
            handle.write(content)
        sftp.chmod(path, mode)
    finally:
        sftp.close()


def main() -> None:
    cloud_password = os.environ.get("VISIONBRIDGE_SSH_PASSWORD", "")
    pi_password = os.environ.get("VISIONBRIDGE_PI_PASSWORD", "")
    if not CLOUD_HOST or not PI_HOST:
        raise SystemExit("VISIONBRIDGE_CLOUD_HOST and VISIONBRIDGE_EDGE_HOST are required")
    if not cloud_password or not pi_password:
        raise SystemExit("VISIONBRIDGE_SSH_PASSWORD and VISIONBRIDGE_PI_PASSWORD are required")
    media_archive = DEPLOY_ROOT / f"mediamtx_v{MEDIA_VERSION}_linux_amd64.tar.gz"
    if not media_archive.is_file() or hashlib.sha256(media_archive.read_bytes()).hexdigest() != MEDIA_SHA256:
        raise SystemExit("verified MediaMTX release archive is missing or invalid")

    cloud = connect(CLOUD_HOST, CLOUD_USER, cloud_password)
    pi = None
    try:
        upload(cloud, DEPLOY_ROOT / "mediamtx" / "mediamtx.yml.template", "/tmp/visionbridge-mediamtx.yml.template")
        upload(cloud, DEPLOY_ROOT / "coturn" / "turnserver.conf.template", "/tmp/visionbridge-turnserver.conf.template")
        upload(cloud, DEPLOY_ROOT / "systemd" / "visionbridge-mediamtx.service", "/tmp/visionbridge-mediamtx.service")
        upload(cloud, media_archive, "/tmp/mediamtx.tar.gz", 0o600)
        cloud_result = run(cloud, fr"""set -Eeuo pipefail
export DEBIAN_FRONTEND=noninteractive
timeout 300 apt-get update -qq
timeout 300 apt-get install -y -qq coturn curl ca-certificates >/dev/null

install -d -m 0750 -o visionbridge -g visionbridge /etc/visionbridge /var/lib/visionbridge
touch /etc/visionbridge/api.env
chmod 600 /etc/visionbridge/api.env

MEDIA_SECRET=$(sed -n 's/^VISIONBRIDGE_MEDIA_PUBLISH_SECRET=//p' /etc/visionbridge/api.env | tail -n1)
TURN_SECRET=$(sed -n 's/^VISIONBRIDGE_TURN_SECRET=//p' /etc/visionbridge/api.env | tail -n1)
[ -n "$MEDIA_SECRET" ] || MEDIA_SECRET=$(openssl rand -hex 32)
[ -n "$TURN_SECRET" ] || TURN_SECRET=$(openssl rand -hex 32)
grep -vE '^(VISIONBRIDGE_MEDIA_PUBLISH_SECRET|VISIONBRIDGE_TURN_SECRET|VISIONBRIDGE_MEDIA_API_URL)=' /etc/visionbridge/api.env > /tmp/visionbridge-api.env
printf 'VISIONBRIDGE_MEDIA_PUBLISH_SECRET=%s\nVISIONBRIDGE_TURN_SECRET=%s\nVISIONBRIDGE_MEDIA_API_URL=http://127.0.0.1:9997\n' "$MEDIA_SECRET" "$TURN_SECRET" >> /tmp/visionbridge-api.env
install -m 0600 -o root -g root /tmp/visionbridge-api.env /etc/visionbridge/api.env
rm -f /tmp/visionbridge-api.env

echo "{MEDIA_SHA256}  /tmp/mediamtx.tar.gz" | sha256sum -c -
tar -xzf /tmp/mediamtx.tar.gz -C /tmp mediamtx
install -m 0755 /tmp/mediamtx /usr/local/bin/mediamtx

sed -e 's/__PUBLIC_IP__/{CLOUD_HOST}/g' -e "s/__TURN_SECRET__/$TURN_SECRET/g" \
  /tmp/visionbridge-mediamtx.yml.template > /tmp/mediamtx.yml
install -m 0640 -o root -g visionbridge /tmp/mediamtx.yml /etc/visionbridge/mediamtx.yml
sed -e 's/__PUBLIC_IP__/{CLOUD_HOST}/g' -e "s/__TURN_SECRET__/$TURN_SECRET/g" \
  /tmp/visionbridge-turnserver.conf.template > /tmp/turnserver.conf
install -m 0600 -o root -g root /tmp/turnserver.conf /etc/turnserver.conf
install -m 0644 /tmp/visionbridge-mediamtx.service /etc/systemd/system/visionbridge-mediamtx.service

if ! id visionbridge-media >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash visionbridge-media
fi
install -d -m 0700 -o visionbridge-media -g visionbridge-media /home/visionbridge-media/.ssh
cat > /etc/ssh/sshd_config.d/visionbridge-media.conf <<'EOF'
Match User visionbridge-media
    PasswordAuthentication no
    PubkeyAuthentication yes
    AllowTcpForwarding local
    PermitOpen 127.0.0.1:8554
    GatewayPorts no
    X11Forwarding no
    PermitTTY no
EOF
sshd -t

if grep -q '^TURNSERVER_ENABLED=' /etc/default/coturn; then
  sed -i 's/^TURNSERVER_ENABLED=.*/TURNSERVER_ENABLED=1/' /etc/default/coturn
else
  printf '\nTURNSERVER_ENABLED=1\n' >> /etc/default/coturn
fi

systemctl daemon-reload
systemctl restart visionbridge-api
systemctl enable --now coturn visionbridge-mediamtx
systemctl restart ssh
sleep 2
systemctl is-active visionbridge-api visionbridge-mediamtx coturn
curl -fsS http://127.0.0.1:9997/v3/paths/list >/dev/null
ss -lntup | grep -E ':(3478|8189|8554|8888|8889|9997)([[:space:]]|$)' | sed -E 's/users:\(.*\)//' || true
echo cloud-media-stack-ready
""")
        print(cloud_result, end="")

        media_secret = read_remote(cloud, "/etc/visionbridge/api.env")
        media_secret = next(
            line.split("=", 1)[1]
            for line in media_secret.splitlines()
            if line.startswith("VISIONBRIDGE_MEDIA_PUBLISH_SECRET=")
        )
        cloud_host_key = read_remote(cloud, "/etc/ssh/ssh_host_ed25519_key.pub")
        key_parts = cloud_host_key.split()
        known_host_line = f"{CLOUD_HOST} {key_parts[0]} {key_parts[1]}\n"

        pi = connect(PI_HOST, "pi", pi_password)
        upload(pi, EDGE_ROOT / "run_visionbridge_media_publisher.sh", "/tmp/run_visionbridge_media_publisher.sh", 0o755)
        upload(pi, EDGE_ROOT / "visionbridge-media-publisher.service", "/tmp/visionbridge-media-publisher.service")
        upload(pi, EDGE_ROOT / "visionbridge-media-tunnel.service", "/tmp/visionbridge-media-tunnel.service")
        run(pi, """set -Eeuo pipefail
sudo install -d -m 0755 /opt/visionbridge
sudo install -d -m 0750 -o root -g pi /etc/visionbridge
sudo install -m 0755 /tmp/run_visionbridge_media_publisher.sh /opt/visionbridge/run_visionbridge_media_publisher.sh
sudo install -m 0644 /tmp/visionbridge-media-publisher.service /etc/systemd/system/visionbridge-media-publisher.service
sudo install -m 0644 /tmp/visionbridge-media-tunnel.service /etc/systemd/system/visionbridge-media-tunnel.service
sudo timeout 300 apt-get update -qq
sudo timeout 300 apt-get install -y -qq autossh >/dev/null
install -d -m 0700 /home/pi/.ssh
if [ ! -f /home/pi/.ssh/visionbridge_media_ed25519 ]; then
  ssh-keygen -q -t ed25519 -N '' -C visionbridge-media-publisher -f /home/pi/.ssh/visionbridge_media_ed25519
fi
sudo systemctl daemon-reload
echo pi-media-files-ready
""")
        write_remote(pi, "/tmp/visionbridge_known_host", known_host_line, 0o600)
        publisher_env = (
            f"VISIONBRIDGE_DEVICE_ID={DEVICE_ID}\n"
            f"VISIONBRIDGE_MEDIA_PUBLISH_SECRET={media_secret}\n"
            "VISIONBRIDGE_PREVIEW_URL=http://127.0.0.1:8090/stream.raw\n"
            "VISIONBRIDGE_MEDIA_INPUT_FORMAT=rawvideo\n"
            f"VISIONBRIDGE_CLOUD_SSH_HOST={CLOUD_HOST}\n"
            "VISIONBRIDGE_MEDIA_RTSP_HOST=127.0.0.1\n"
            "VISIONBRIDGE_MEDIA_RTSP_PORT=18554\n"
            "VISIONBRIDGE_MEDIA_FPS=15\n"
            "VISIONBRIDGE_MEDIA_WIDTH=320\n"
            "VISIONBRIDGE_MEDIA_HEIGHT=240\n"
            "VISIONBRIDGE_MEDIA_BITRATE=600k\n"
            "VISIONBRIDGE_MEDIA_ENCODER=h264_v4l2m2m\n"
        )
        write_remote(pi, "/tmp/media-publisher.env", publisher_env, 0o600)
        public_key = read_remote(pi, "/home/pi/.ssh/visionbridge_media_ed25519.pub")
        authorized = f'restrict,port-forwarding,permitopen="127.0.0.1:8554" {public_key}\n'
        write_remote(cloud, "/tmp/visionbridge-media-authorized-key", authorized, 0o600)
        run(cloud, """set -Eeuo pipefail
install -m 0600 -o visionbridge-media -g visionbridge-media /tmp/visionbridge-media-authorized-key /home/visionbridge-media/.ssh/authorized_keys
""")
        pi_result = run(pi, fr"""set -Eeuo pipefail
touch /home/pi/.ssh/known_hosts
chmod 600 /home/pi/.ssh/known_hosts
grep -v '^{CLOUD_HOST} ' /home/pi/.ssh/known_hosts > /tmp/known_hosts.preserved || true
cat /tmp/visionbridge_known_host >> /tmp/known_hosts.preserved
install -m 0600 -o pi -g pi /tmp/known_hosts.preserved /home/pi/.ssh/known_hosts
sudo install -m 0640 -o root -g pi /tmp/media-publisher.env /etc/visionbridge/media-publisher.env
rm -f /tmp/media-publisher.env
sudo systemctl enable --now visionbridge-media-tunnel.service
for i in $(seq 1 20); do
  if timeout 1 bash -c '</dev/tcp/127.0.0.1/18554' 2>/dev/null; then break; fi
  sleep 1
done
timeout 1 bash -c '</dev/tcp/127.0.0.1/18554'
sudo systemctl enable --now visionbridge-media-publisher.service
sleep 8
sudo systemctl is-active visionbridge-media-tunnel.service visionbridge-media-publisher.service
curl -fsS http://127.0.0.1:8090/status.json >/dev/null
echo pi-media-publisher-ready
""", timeout=180)
        print(pi_result, end="")

        final = run(cloud, fr"""set -Eeuo pipefail
for i in $(seq 1 30); do
  READY=$(curl -fsS http://127.0.0.1:9997/v3/paths/list | python3 -c 'import json,sys; d=json.load(sys.stdin); print(any(x.get("name") == "devices/{DEVICE_ID}" and x.get("ready") for x in d.get("items", [])))')
  [ "$READY" = True ] && break
  sleep 1
done
[ "$READY" = True ]
curl -fsS http://127.0.0.1:8889/devices/{DEVICE_ID}/ >/dev/null
curl -fsS http://127.0.0.1:8888/devices/{DEVICE_ID}/ >/dev/null
curl -fsS http://127.0.0.1:8000/api/v1/devices | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["items"][0]["streamStatus"] == "live"; print("device-api-stream=live")'
echo media-end-to-end-ready
""", timeout=120)
        print(final, end="")
    finally:
        if pi is not None:
            pi.close()
        cloud.close()


if __name__ == "__main__":
    main()
