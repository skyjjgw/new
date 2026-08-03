#!/usr/bin/env python3
"""Poll the existing edge preview status and mirror it to VisionBridge Cloud."""

from __future__ import annotations

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
from pathlib import Path


STATUS_URL = os.getenv("VISIONBRIDGE_EDGE_STATUS_URL", "http://127.0.0.1:8090/status.json")
CLOUD_URL = os.getenv("VISIONBRIDGE_CLOUD_URL", "http://115.231.176.136:8088/api/v1/telemetry")
TOKEN = os.getenv("VISIONBRIDGE_INGEST_TOKEN", "")
INTERVAL = max(2, int(os.getenv("VISIONBRIDGE_UPLOAD_INTERVAL", "5")))
SNAPSHOT_DIR = Path(os.getenv("VISIONBRIDGE_SNAPSHOT_DIR", "/home/pi/blind_occupancy/snapshots"))
MAX_SNAPSHOT_BYTES = 4 * 1024 * 1024
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def post_json(url: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {TOKEN}", "User-Agent": "VisionBridgeEdge/1.0"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        if response.status not in (200, 201, 202):
            raise RuntimeError(f"cloud returned {response.status}")


def attach_snapshot(status: dict, last_uploaded: str) -> str:
    runtime = status.get("runtime", {})
    name = Path(str(runtime.get("last_snapshot_name") or "")).name
    if not name or name == last_uploaded or not int(runtime.get("snapshot_ready") or 0):
        return last_uploaded
    path = SNAPSHOT_DIR / name
    if not path.is_file() or path.stat().st_size > MAX_SNAPSHOT_BYTES:
        return last_uploaded
    status["snapshot_filename"] = name
    status["snapshot_b64"] = base64.b64encode(path.read_bytes()).decode("ascii")
    return name


def main() -> None:
    if not TOKEN:
        raise SystemExit("VISIONBRIDGE_INGEST_TOKEN is required")
    failures = 0
    last_snapshot = ""
    while True:
        try:
            status = get_json(STATUS_URL)
            pending_snapshot = attach_snapshot(status, last_snapshot)
            post_json(CLOUD_URL, status)
            last_snapshot = pending_snapshot
            if failures:
                logging.info("cloud link restored")
            failures = 0
        except (OSError, ValueError, RuntimeError, urllib.error.URLError) as exc:
            failures += 1
            logging.warning("upload failed (%s): %s", failures, exc)
        time.sleep(min(60, INTERVAL * max(1, min(failures, 6))))


if __name__ == "__main__":
    main()
