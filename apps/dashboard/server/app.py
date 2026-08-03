from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import threading
import urllib.error
import urllib.request
import uuid
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("VISIONBRIDGE_DATA_DIR", BASE_DIR / "data"))
DB_PATH = DATA_DIR / "visionbridge.db"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
VOLUNTEER_UPLOAD_DIR = DATA_DIR / "volunteer_uploads"
INGEST_TOKEN = os.getenv("VISIONBRIDGE_INGEST_TOKEN", "")
AUTH_SECRET = os.getenv("VISIONBRIDGE_AUTH_SECRET", INGEST_TOKEN or "visionbridge-development-only")
SEED_DEMO_DATA = os.getenv("VISIONBRIDGE_SEED_DEMO_DATA", "1") == "1"
DEFAULT_LNG = float(os.getenv("VISIONBRIDGE_DEFAULT_LNG", "121.138923"))
DEFAULT_LAT = float(os.getenv("VISIONBRIDGE_DEFAULT_LAT", "28.632112"))
SMTP_HOST = os.getenv("VISIONBRIDGE_SMTP_HOST", "smtp.qq.com")
SMTP_PORT = int(os.getenv("VISIONBRIDGE_SMTP_PORT", "465"))
SMTP_USER = os.getenv("VISIONBRIDGE_SMTP_USER", "")
SMTP_AUTH_CODE = os.getenv("VISIONBRIDGE_SMTP_AUTH_CODE", "")
SMTP_FROM_NAME = os.getenv("VISIONBRIDGE_SMTP_FROM_NAME", "视桥志愿者平台")
MEDIA_API_URL = os.getenv("VISIONBRIDGE_MEDIA_API_URL", "http://127.0.0.1:9997").rstrip("/")
MEDIA_PUBLISH_SECRET = os.getenv("VISIONBRIDGE_MEDIA_PUBLISH_SECRET", "")
EMAIL_DEBUG = os.getenv("VISIONBRIDGE_EMAIL_DEBUG", "0") == "1"
AUTH_CODE_TTL_MINUTES = 10
AUTH_TOKEN_TTL_DAYS = 30
MAX_UPLOAD_BYTES = 8 * 1024 * 1024
TZ = timezone(timedelta(hours=8))
DB_LOCK = threading.RLock()

EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
REPORT_CATEGORIES = {
    "temporary_obstacle": "临时杂物/堆放",
    "shop_step": "店铺台阶/固定高差",
    "construction": "临时施工",
    "road_damage": "路面坑洼/破损",
    "vehicle": "车辆占用",
    "other": "其他障碍",
}
CLEANUP_REASONS = {
    "unable_now": "当时不方便清理",
    "fixed_barrier": "固定障碍无法移动",
    "unsafe_to_clear": "不具备安全处理条件",
}
PRIORITY_SEVERITY = {"low": "attention", "normal": "warning", "urgent": "critical"}


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def parse_time(value: str | None) -> datetime:
    if not value:
        return datetime.now(TZ)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=TZ)
    except ValueError:
        return datetime.now(TZ)


@contextmanager
def db():
    connection = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        yield connection
    finally:
        connection.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    VOLUNTEER_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    with DB_LOCK, db() as connection:
        connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS devices (
              device_id TEXT PRIMARY KEY,
              name TEXT NOT NULL,
              point_name TEXT NOT NULL,
              last_seen TEXT NOT NULL,
              status TEXT NOT NULL,
              payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS telemetry (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              device_id TEXT NOT NULL,
              received_at TEXT NOT NULL,
              source_ts TEXT NOT NULL,
              payload TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_telemetry_device_time ON telemetry(device_id, received_at DESC);
            CREATE TABLE IF NOT EXISTS events (
              id TEXT PRIMARY KEY,
              source_event_id TEXT,
              device_id TEXT NOT NULL,
              type TEXT NOT NULL,
              type_label TEXT NOT NULL,
              status TEXT NOT NULL,
              severity TEXT NOT NULL,
              confidence INTEGER NOT NULL DEFAULT 0,
              point_name TEXT NOT NULL,
              address TEXT NOT NULL,
              lat REAL NOT NULL,
              lng REAL NOT NULL,
              snapshot_url TEXT,
              source TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              duration_sec INTEGER NOT NULL DEFAULT 0
            );
            CREATE UNIQUE INDEX IF NOT EXISTS idx_events_source ON events(source_event_id) WHERE source_event_id IS NOT NULL AND source_event_id <> '';
            CREATE TABLE IF NOT EXISTS users (
              id TEXT PRIMARY KEY,
              email TEXT NOT NULL UNIQUE,
              display_name TEXT NOT NULL,
              role TEXT NOT NULL DEFAULT 'volunteer',
              status TEXT NOT NULL DEFAULT 'active',
              email_verified_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS email_verification_codes (
              email TEXT NOT NULL,
              purpose TEXT NOT NULL,
              code_hash TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              attempts INTEGER NOT NULL DEFAULT 0,
              consumed_at TEXT,
              last_sent_at TEXT NOT NULL,
              window_started_at TEXT NOT NULL,
              request_count INTEGER NOT NULL DEFAULT 1,
              PRIMARY KEY(email, purpose)
            );
            CREATE TABLE IF NOT EXISTS auth_sessions (
              token_hash TEXT PRIMARY KEY,
              user_id TEXT NOT NULL,
              expires_at TEXT NOT NULL,
              created_at TEXT NOT NULL,
              revoked_at TEXT,
              FOREIGN KEY(user_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_auth_sessions_user ON auth_sessions(user_id, expires_at DESC);
            CREATE TABLE IF NOT EXISTS volunteer_reports (
              id TEXT PRIMARY KEY,
              reporter_id TEXT NOT NULL,
              category TEXT NOT NULL,
              cleanup_reason TEXT NOT NULL,
              description TEXT NOT NULL,
              address TEXT NOT NULL,
              lat REAL NOT NULL,
              lng REAL NOT NULL,
              photo_filename TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'pending',
              priority TEXT NOT NULL DEFAULT 'normal',
              review_note TEXT NOT NULL DEFAULT '',
              reviewed_by TEXT,
              reviewed_at TEXT,
              obstacle_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY(reporter_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_reports_status_time ON volunteer_reports(status, created_at DESC);
            CREATE TABLE IF NOT EXISTS obstacles (
              id TEXT PRIMARY KEY,
              report_id TEXT NOT NULL UNIQUE,
              event_id TEXT NOT NULL UNIQUE,
              category TEXT NOT NULL,
              category_label TEXT NOT NULL,
              description TEXT NOT NULL,
              address TEXT NOT NULL,
              lat REAL NOT NULL,
              lng REAL NOT NULL,
              photo_filename TEXT NOT NULL,
              priority TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'open',
              source TEXT NOT NULL DEFAULT 'volunteer',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              resolved_at TEXT,
              FOREIGN KEY(report_id) REFERENCES volunteer_reports(id),
              FOREIGN KEY(event_id) REFERENCES events(id)
            );
            CREATE INDEX IF NOT EXISTS idx_obstacles_status_time ON obstacles(status, created_at DESC);
            CREATE TABLE IF NOT EXISTS public_tasks (
              id TEXT PRIMARY KEY,
              obstacle_id TEXT NOT NULL,
              title TEXT NOT NULL,
              description TEXT NOT NULL,
              priority TEXT NOT NULL,
              status TEXT NOT NULL DEFAULT 'open',
              assignee_id TEXT,
              completion_note TEXT NOT NULL DEFAULT '',
              completion_photo_filename TEXT,
              review_note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              claimed_at TEXT,
              submitted_at TEXT,
              verified_at TEXT,
              FOREIGN KEY(obstacle_id) REFERENCES obstacles(id),
              FOREIGN KEY(assignee_id) REFERENCES users(id)
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status_time ON public_tasks(status, created_at DESC);
            CREATE TABLE IF NOT EXISTS task_activity (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              task_id TEXT NOT NULL,
              actor_id TEXT,
              action TEXT NOT NULL,
              note TEXT NOT NULL DEFAULT '',
              created_at TEXT NOT NULL,
              FOREIGN KEY(task_id) REFERENCES public_tasks(id)
            );
            """
        )
        if SEED_DEMO_DATA and connection.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
            now = datetime.now(TZ)
            samples = [
                ("VB-DEMO-006", "construction_obstacle", "施工杂物占用", "active", "critical", 91, "学院路东侧盲道", "学院路与求知路交叉口东南侧", DEFAULT_LAT + .00025, DEFAULT_LNG + .00029, now - timedelta(minutes=7), 428),
                ("VB-DEMO-005", "non_motor_vehicle", "非机动车占用", "dispatched", "warning", 87, "博学路北段", "博学路公交站向北 120 米", DEFAULT_LAT - .00037, DEFAULT_LNG - .00050, now - timedelta(minutes=31), 1280),
                ("VB-DEMO-004", "motor_vehicle", "两轮机动车占用", "cleared", "warning", 84, "求知路西侧盲道", "求知路 18 号门前", DEFAULT_LAT + .00057, DEFAULT_LNG - .00103, now - timedelta(minutes=83), 620),
            ]
            for item in samples:
                event_id, event_type, label, status, severity, confidence, point, address, lat, lng, created, duration = item
                connection.execute(
                    "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (event_id, None, "demo-device", event_type, label, status, severity, confidence, point, address, lat, lng, None, "历史演示样例", created.isoformat(timespec="seconds"), now.isoformat(timespec="seconds"), duration),
                )
        connection.commit()


def event_label(event_type: str) -> str:
    return {
        "non_motor_vehicle": "非机动车占用",
        "motor_vehicle": "两轮机动车占用",
        "construction_obstacle": "施工杂物占用",
        "person": "行人滞留",
    }.get(event_type, "其他障碍物占用")


def severity_for(alert_code: int, confidence: int) -> str:
    if alert_code >= 3 or confidence >= 90:
        return "critical"
    if alert_code >= 2 or confidence >= 70:
        return "warning"
    return "attention"


def status_label(status: str) -> str:
    return {"suspected": "疑似", "active": "未接单", "dispatched": "处置中", "cleared": "已闭环"}.get(status, status)


def normalize_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 254 or not EMAIL_PATTERN.fullmatch(email):
        raise HTTPException(status_code=422, detail="invalid email address")
    return email


def digest_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def verification_digest(email: str, purpose: str, code: str) -> str:
    message = f"{email}:{purpose}:{code}".encode("utf-8")
    return hmac.new(AUTH_SECRET.encode("utf-8"), message, hashlib.sha256).hexdigest()


def send_verification_email(recipient: str, code: str) -> None:
    if EMAIL_DEBUG:
        return
    if not SMTP_USER or not SMTP_AUTH_CODE:
        raise HTTPException(status_code=503, detail="email service is not configured")
    message = EmailMessage()
    message["Subject"] = "视桥志愿者平台登录验证码"
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    message["To"] = recipient
    message.set_content(
        f"您的验证码是：{code}\n\n验证码 {AUTH_CODE_TTL_MINUTES} 分钟内有效。若非本人操作，请忽略此邮件。"
    )
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=12, context=context) as client:
            client.login(SMTP_USER, SMTP_AUTH_CODE)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise HTTPException(status_code=502, detail="verification email could not be sent") from exc


def user_from_authorization(authorization: str | None) -> sqlite3.Row:
    token = (authorization or "").removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(status_code=401, detail="missing user token")
    token_hash = digest_text(token)
    with DB_LOCK, db() as connection:
        row = connection.execute(
            "SELECT u.* FROM auth_sessions s JOIN users u ON u.id=s.user_id "
            "WHERE s.token_hash=? AND s.revoked_at IS NULL AND u.status='active'",
            (token_hash,),
        ).fetchone()
        session = connection.execute(
            "SELECT expires_at FROM auth_sessions WHERE token_hash=? AND revoked_at IS NULL",
            (token_hash,),
        ).fetchone()
    if row is None or session is None or parse_time(session["expires_at"]) <= datetime.now(TZ):
        raise HTTPException(status_code=401, detail="invalid or expired user token")
    return row


def current_user(authorization: str | None = Header(default=None)) -> sqlite3.Row:
    return user_from_authorization(authorization)


def user_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "displayName": row["display_name"],
        "role": row["role"],
        "createdAt": row["created_at"],
    }


def report_payload(row: sqlite3.Row, photo_scope: str = "volunteer") -> dict[str, Any]:
    report_id = row["id"]
    photo_url = (
        f"/api/v1/admin/reports/{report_id}/photo"
        if photo_scope == "admin"
        else f"/api/v1/volunteer/reports/{report_id}/photo"
    )
    return {
        "id": report_id,
        "reporterId": row["reporter_id"],
        "category": row["category"],
        "categoryLabel": REPORT_CATEGORIES.get(row["category"], "其他障碍"),
        "cleanupReason": row["cleanup_reason"],
        "cleanupReasonLabel": CLEANUP_REASONS.get(row["cleanup_reason"], row["cleanup_reason"]),
        "description": row["description"],
        "address": row["address"],
        "lat": row["lat"],
        "lng": row["lng"],
        "photoUrl": photo_url,
        "status": row["status"],
        "canDelete": row["status"] in {"pending", "rejected"},
        "priority": row["priority"],
        "reviewNote": row["review_note"],
        "obstacleId": row["obstacle_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def obstacle_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "eventId": row["event_id"],
        "category": row["category"],
        "categoryLabel": row["category_label"],
        "description": row["description"],
        "address": row["address"],
        "lat": row["lat"],
        "lng": row["lng"],
        "photoUrl": f"/api/v1/obstacles/{row['id']}/photo",
        "priority": row["priority"],
        "status": row["status"],
        "source": row["source"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "taskId": row["task_id"] if "task_id" in row.keys() else None,
        "taskStatus": row["task_status"] if "task_status" in row.keys() else None,
    }


def task_payload(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "obstacleId": row["obstacle_id"],
        "title": row["title"],
        "description": row["description"],
        "priority": row["priority"],
        "status": row["status"],
        "assigneeId": row["assignee_id"],
        "assigneeName": row["assignee_name"] if "assignee_name" in row.keys() else None,
        "assigneeEmail": row["assignee_email"] if "assignee_email" in row.keys() else None,
        "completionNote": row["completion_note"],
        "reviewNote": row["review_note"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "claimedAt": row["claimed_at"],
        "submittedAt": row["submitted_at"],
        "verifiedAt": row["verified_at"],
        "category": row["category"],
        "categoryLabel": row["category_label"],
        "address": row["address"],
        "lat": row["lat"],
        "lng": row["lng"],
        "photoUrl": f"/api/v1/obstacles/{row['obstacle_id']}/photo",
    }


def save_upload(upload: UploadFile, content: bytes, prefix: str) -> str:
    content_type = (upload.content_type or "").lower()
    suffix = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}.get(content_type)
    if suffix is None:
        raise HTTPException(status_code=415, detail="only JPEG, PNG and WebP images are supported")
    if not content or len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="image must be between 1 byte and 8 MiB")
    filename = f"{prefix}-{uuid.uuid4().hex}{suffix}"
    (VOLUNTEER_UPLOAD_DIR / filename).write_bytes(content)
    return filename


def task_join_query(where: str = "") -> str:
    return (
        "SELECT t.*,o.category,o.category_label,o.address,o.lat,o.lng,"
        "u.display_name AS assignee_name,u.email AS assignee_email "
        "FROM public_tasks t JOIN obstacles o ON o.id=t.obstacle_id "
        "LEFT JOIN users u ON u.id=t.assignee_id " + where
    )


def row_to_event(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "type": row["type"],
        "typeLabel": row["type_label"],
        "status": row["status"],
        "statusLabel": status_label(row["status"]),
        "severity": row["severity"],
        "confidence": row["confidence"],
        "pointName": row["point_name"],
        "address": row["address"],
        "lat": row["lat"],
        "lng": row["lng"],
        "snapshotUrl": row["snapshot_url"],
        "source": row["source"],
        "createdAt": row["created_at"],
        "durationSec": row["duration_sec"],
    }


def stream_path_for_device(device_id: str) -> str:
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "-", device_id).strip("-") or "unknown"
    return f"devices/{safe_id}"


def default_device_name(device_id: str) -> str:
    match = re.search(r"(\d+)$", device_id)
    suffix = f"{int(match.group(1)):02d}" if match else device_id[-6:].upper()
    return f"视桥移动巡检终端 {suffix}"


def media_paths() -> dict[str, dict[str, Any]]:
    try:
        request = urllib.request.Request(
            f"{MEDIA_API_URL}/v3/paths/list",
            headers={"Accept": "application/json", "User-Agent": "VisionBridge-API/1.0"},
        )
        with urllib.request.urlopen(request, timeout=1.2) as response:
            body = json.loads(response.read().decode("utf-8"))
        return {
            str(item.get("name")): item
            for item in body.get("items", [])
            if isinstance(item, dict) and item.get("name")
        }
    except (OSError, ValueError, urllib.error.URLError):
        return {}


def normalize_device(row: sqlite3.Row | None, paths: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    if row is None:
        stream_path = stream_path_for_device("uno-cloud-gateway-01")
        return {
            "id": "uno-cloud-gateway-01", "name": "视桥移动巡检终端 01", "status": "offline",
            "pointName": "blindway-point-01", "lastSeen": "", "cameraStatus": "等待接入", "gpsStatus": "等待接入",
            "cameraFps": 0, "inferenceMs": 0, "inferenceFps": 0, "sats": 0, "hdop": 0, "lat": DEFAULT_LAT, "lng": DEFAULT_LNG,
            "model": "YOLOv8 · ONNX v1", "streamPath": stream_path, "streamStatus": "offline",
            "streamReaders": 0, "webRtcUrl": f"/webrtc/{stream_path}/", "hlsUrl": f"/hls/{stream_path}/",
        }
    payload = json.loads(row["payload"])
    runtime = payload.get("runtime", {})
    gps = payload.get("gps", {})
    props = payload.get("iot_properties", {})
    seen = parse_time(row["last_seen"])
    online = (datetime.now(TZ) - seen.astimezone(TZ)).total_seconds() < 90
    lat = gps.get("lat") or (props.get("gpsLatE6", 0) / 1_000_000) or DEFAULT_LAT
    lng = gps.get("lng") or (props.get("gpsLngE6", 0) / 1_000_000) or DEFAULT_LNG
    stream_path = stream_path_for_device(row["device_id"])
    media_path = (paths or {}).get(stream_path, {})
    stream_ready = bool(media_path.get("ready"))
    readers = media_path.get("readers") or []
    return {
        "id": row["device_id"], "name": row["name"], "status": "online" if online else "offline",
        "pointName": row["point_name"], "lastSeen": row["last_seen"],
        "cameraStatus": "streaming" if props.get("cameraStatusCode") == 1 else runtime.get("camera_status", "unknown"),
        "gpsStatus": "connected" if props.get("gpsStatusCode") == 1 else gps.get("status", "unknown"),
        "cameraFps": round(float(runtime.get("camera_fps") or props.get("cameraFpsX100", 0) / 100), 1),
        "inferenceMs": int(runtime.get("inference_ms") or props.get("inferenceMs", 0)),
        "inferenceFps": round(float(runtime.get("inference_fps") or 0), 2),
        "sats": int(gps.get("num_sats") or props.get("numSats", 0)),
        "hdop": round(float(gps.get("hdop") or props.get("hdopX100", 0) / 100), 2),
        "lat": float(lat), "lng": float(lng), "model": "YOLOv8 · ONNX v1",
        "streamPath": stream_path, "streamStatus": "live" if stream_ready else "offline",
        "streamReaders": len(readers) if isinstance(readers, list) else 0,
        "webRtcUrl": f"/webrtc/{stream_path}/", "hlsUrl": f"/hls/{stream_path}/",
    }


class EventAction(BaseModel):
    action: Literal["dispatch", "clear"]


class EmailCodeRequest(BaseModel):
    email: str
    purpose: Literal["login"] = "login"


class EmailCodeVerify(BaseModel):
    email: str
    code: str = Field(min_length=6, max_length=6)
    purpose: Literal["login"] = "login"
    display_name: str | None = Field(default=None, min_length=1, max_length=30, alias="displayName")


class AdminReportReview(BaseModel):
    action: Literal["approve", "reject"]
    note: str = Field(default="", max_length=500)
    publish_task: bool = Field(default=True, alias="publishTask")
    priority: Literal["low", "normal", "urgent"] = "normal"


class AdminTaskReview(BaseModel):
    action: Literal["verify", "return", "cancel", "reopen"]
    note: str = Field(default="", max_length=500)


class TelemetryEnvelope(BaseModel):
    ts: str | None = None
    device: dict[str, Any] = Field(default_factory=dict)
    runtime: dict[str, Any] = Field(default_factory=dict)
    gps: dict[str, Any] = Field(default_factory=dict)
    iot_properties: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, Any] = Field(default_factory=dict)
    dispatch: dict[str, Any] = Field(default_factory=dict)
    snapshot_b64: str | None = None
    snapshot_filename: str | None = None


class MediaAuthRequest(BaseModel):
    user: str = ""
    password: str = ""
    token: str = ""
    ip: str = ""
    action: str = ""
    path: str = ""
    protocol: str = ""
    id: str = ""
    query: str = ""


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="VisionBridge Cloud API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("VISIONBRIDGE_CORS_ORIGINS", "*").split(",")],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    location = ".".join(str(part) for part in (errors[0].get("loc", []) if errors else []))
    if "displayName" in location or "display_name" in location:
        detail = "志愿者昵称请填写 1–30 个字符，也可以留空使用默认昵称"
    elif "code" in location:
        detail = "请输入邮件中的 6 位验证码"
    elif "email" in location:
        detail = "请输入有效的邮箱地址"
    else:
        detail = "提交内容格式不正确，请检查后重试"
    return JSONResponse(status_code=422, content={"detail": detail})


@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "service": "visionbridge-api", "time": now_iso()}


@app.post("/api/v1/media/auth")
def authorize_media(request: MediaAuthRequest) -> dict[str, bool]:
    clean_path = (request.path or "").strip("/")
    valid_path = re.fullmatch(r"devices/[a-zA-Z0-9_-]+", clean_path) is not None
    if request.action in {"read", "playback"} and valid_path:
        return {"authorized": True}
    if request.action == "publish" and request.protocol == "rtsp" and valid_path:
        expected_path = stream_path_for_device(request.user)
        if (
            MEDIA_PUBLISH_SECRET
            and hmac.compare_digest(request.password, MEDIA_PUBLISH_SECRET)
            and hmac.compare_digest(clean_path, expected_path)
        ):
            return {"authorized": True}
    raise HTTPException(status_code=401, detail="media authorization denied")


@app.get("/api/v1/config/public")
def public_config() -> dict[str, Any]:
    return {
        "amapKey": os.getenv("AMAP_JS_KEY", ""),
        "amapSecurityCode": os.getenv("AMAP_SECURITY_CODE", ""),
        "defaultCenter": [DEFAULT_LNG, DEFAULT_LAT],
    }


@app.post("/api/v1/auth/email/request")
def request_email_code(payload: EmailCodeRequest) -> dict[str, Any]:
    email = normalize_email(payload.email)
    purpose = payload.purpose
    current = datetime.now(TZ)
    with DB_LOCK, db() as connection:
        row = connection.execute(
            "SELECT * FROM email_verification_codes WHERE email=? AND purpose=?",
            (email, purpose),
        ).fetchone()
    request_count = 1
    window_started = current
    if row is not None:
        last_sent = parse_time(row["last_sent_at"])
        if (current - last_sent).total_seconds() < 60:
            raise HTTPException(status_code=429, detail="please wait before requesting another code")
        window_started = parse_time(row["window_started_at"])
        if (current - window_started).total_seconds() >= 3600:
            window_started = current
        else:
            request_count = int(row["request_count"]) + 1
            if request_count > 5:
                raise HTTPException(status_code=429, detail="too many verification emails")

    code = f"{secrets.randbelow(1_000_000):06d}"
    send_verification_email(email, code)
    sent_at = current.isoformat(timespec="seconds")
    expires_at = (current + timedelta(minutes=AUTH_CODE_TTL_MINUTES)).isoformat(timespec="seconds")
    with DB_LOCK, db() as connection:
        connection.execute(
            "INSERT INTO email_verification_codes(email,purpose,code_hash,expires_at,attempts,consumed_at,last_sent_at,window_started_at,request_count) "
            "VALUES(?,?,?,?,0,NULL,?,?,?) ON CONFLICT(email,purpose) DO UPDATE SET "
            "code_hash=excluded.code_hash,expires_at=excluded.expires_at,attempts=0,consumed_at=NULL,last_sent_at=excluded.last_sent_at,"
            "window_started_at=excluded.window_started_at,request_count=excluded.request_count",
            (email, purpose, verification_digest(email, purpose, code), expires_at, sent_at, window_started.isoformat(timespec="seconds"), request_count),
        )
        connection.commit()
    response: dict[str, Any] = {"sent": True, "expiresIn": AUTH_CODE_TTL_MINUTES * 60}
    if EMAIL_DEBUG:
        response["debugCode"] = code
    return response


@app.post("/api/v1/auth/email/verify")
def verify_email_code(payload: EmailCodeVerify) -> dict[str, Any]:
    email = normalize_email(payload.email)
    code = payload.code.strip()
    if not code.isdigit() or len(code) != 6:
        raise HTTPException(status_code=422, detail="verification code must contain 6 digits")
    current = datetime.now(TZ)
    with DB_LOCK, db() as connection:
        row = connection.execute(
            "SELECT * FROM email_verification_codes WHERE email=? AND purpose=?",
            (email, payload.purpose),
        ).fetchone()
        if row is None or row["consumed_at"]:
            raise HTTPException(status_code=400, detail="verification code is unavailable")
        if parse_time(row["expires_at"]) <= current:
            raise HTTPException(status_code=400, detail="verification code has expired")
        if int(row["attempts"]) >= 5:
            raise HTTPException(status_code=429, detail="verification attempts exceeded")
        expected = verification_digest(email, payload.purpose, code)
        if not hmac.compare_digest(expected, row["code_hash"]):
            connection.execute(
                "UPDATE email_verification_codes SET attempts=attempts+1 WHERE email=? AND purpose=?",
                (email, payload.purpose),
            )
            connection.commit()
            raise HTTPException(status_code=400, detail="verification code is incorrect")

        timestamp = current.isoformat(timespec="seconds")
        connection.execute(
            "UPDATE email_verification_codes SET consumed_at=? WHERE email=? AND purpose=?",
            (timestamp, email, payload.purpose),
        )
        user = connection.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        display_name = (payload.display_name or "").strip()
        if user is None:
            display_name = display_name or email.split("@", 1)[0][:30] or "视桥志愿者"
            user_id = f"USR-{uuid.uuid4().hex[:12].upper()}"
            connection.execute(
                "INSERT INTO users(id,email,display_name,role,status,email_verified_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                (user_id, email, display_name, "volunteer", "active", timestamp, timestamp, timestamp),
            )
        else:
            user_id = user["id"]
            if display_name:
                connection.execute("UPDATE users SET display_name=?,updated_at=? WHERE id=?", (display_name, timestamp, user_id))

        token = secrets.token_urlsafe(32)
        token_hash = digest_text(token)
        token_expires = (current + timedelta(days=AUTH_TOKEN_TTL_DAYS)).isoformat(timespec="seconds")
        connection.execute(
            "INSERT INTO auth_sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)",
            (token_hash, user_id, token_expires, timestamp),
        )
        connection.execute("DELETE FROM auth_sessions WHERE expires_at<?", (timestamp,))
        connection.commit()
        user = connection.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    return {"token": token, "tokenType": "Bearer", "expiresAt": token_expires, "user": user_payload(user)}


@app.get("/api/v1/auth/me")
def auth_me(user: sqlite3.Row = Depends(current_user)) -> dict[str, Any]:
    return {"user": user_payload(user)}


@app.post("/api/v1/auth/logout")
def auth_logout(
    authorization: str | None = Header(default=None),
    _: sqlite3.Row = Depends(current_user),
) -> dict[str, Any]:
    token = (authorization or "").removeprefix("Bearer ").strip()
    with DB_LOCK, db() as connection:
        connection.execute("UPDATE auth_sessions SET revoked_at=? WHERE token_hash=?", (now_iso(), digest_text(token)))
        connection.commit()
    return {"loggedOut": True}


@app.post("/api/v1/volunteer/reports", status_code=201)
async def create_volunteer_report(
    category: str = Form(...),
    cleanup_reason: str = Form(..., alias="cleanupReason"),
    description: str = Form(...),
    address: str = Form(default=""),
    lat: float = Form(...),
    lng: float = Form(...),
    photo: UploadFile = File(...),
    user: sqlite3.Row = Depends(current_user),
) -> dict[str, Any]:
    if category not in REPORT_CATEGORIES:
        raise HTTPException(status_code=422, detail="unsupported report category")
    if cleanup_reason not in CLEANUP_REASONS:
        raise HTTPException(status_code=422, detail="unsupported cleanup reason")
    description = description.strip()
    if not 5 <= len(description) <= 500:
        raise HTTPException(status_code=422, detail="description must contain 5 to 500 characters")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(status_code=422, detail="invalid coordinates")
    content = await photo.read(MAX_UPLOAD_BYTES + 1)
    filename = save_upload(photo, content, "report")
    report_id = f"VBR-{datetime.now(TZ).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
    timestamp = now_iso()
    with DB_LOCK, db() as connection:
        connection.execute(
            "INSERT INTO volunteer_reports(id,reporter_id,category,cleanup_reason,description,address,lat,lng,photo_filename,status,priority,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,'pending','normal',?,?)",
            (report_id, user["id"], category, cleanup_reason, description, address.strip() or "志愿者现场上报点位", lat, lng, filename, timestamp, timestamp),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM volunteer_reports WHERE id=?", (report_id,)).fetchone()
    return {"report": report_payload(row)}


@app.get("/api/v1/volunteer/reports/mine")
def my_volunteer_reports(user: sqlite3.Row = Depends(current_user)) -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        rows = connection.execute(
            "SELECT * FROM volunteer_reports WHERE reporter_id=? AND status<>'deleted' ORDER BY created_at DESC LIMIT 200",
            (user["id"],),
        ).fetchall()
    return {"items": [report_payload(row) for row in rows], "count": len(rows)}


@app.delete("/api/v1/volunteer/reports/{report_id}")
def delete_volunteer_report(report_id: str, user: sqlite3.Row = Depends(current_user)) -> dict[str, Any]:
    """Delete an unapproved report owned by the current volunteer.

    Approved reports have already become public obstacle data and must be
    revoked by an operator instead of disappearing from the audit trail.
    """
    filename = ""
    with DB_LOCK, db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        report = connection.execute(
            "SELECT * FROM volunteer_reports WHERE id=? AND reporter_id=?",
            (report_id, user["id"]),
        ).fetchone()
        if report is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="report not found")
        if report["status"] not in {"pending", "rejected"}:
            connection.rollback()
            raise HTTPException(
                status_code=409,
                detail="approved reports are public records and cannot be deleted by the reporter",
            )
        filename = Path(report["photo_filename"]).name
        connection.execute("DELETE FROM volunteer_reports WHERE id=?", (report_id,))
        connection.commit()
    if filename:
        (VOLUNTEER_UPLOAD_DIR / filename).unlink(missing_ok=True)
    return {"deleted": True, "reportId": report_id}


@app.get("/api/v1/volunteer/reports/{report_id}/photo")
def volunteer_report_photo(report_id: str, user: sqlite3.Row = Depends(current_user)):
    from fastapi.responses import FileResponse

    with DB_LOCK, db() as connection:
        row = connection.execute("SELECT * FROM volunteer_reports WHERE id=?", (report_id,)).fetchone()
    if row is None or row["reporter_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="report not found")
    path = VOLUNTEER_UPLOAD_DIR / Path(row["photo_filename"]).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})


@app.get("/api/v1/map/obstacles")
def map_obstacles(include_resolved: bool = Query(default=False, alias="includeResolved")) -> dict[str, Any]:
    query = (
        "SELECT o.*,t.id AS task_id,t.status AS task_status FROM obstacles o "
        "LEFT JOIN public_tasks t ON t.id=(SELECT latest.id FROM public_tasks latest "
        "WHERE latest.obstacle_id=o.id ORDER BY latest.created_at DESC LIMIT 1)"
    )
    if not include_resolved:
        query += " WHERE o.status IN ('open','assigned','resolving')"
    query += " ORDER BY CASE o.priority WHEN 'urgent' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, o.created_at DESC LIMIT 1000"
    with DB_LOCK, db() as connection:
        rows = connection.execute(query).fetchall()
    return {"items": [obstacle_payload(row) for row in rows], "count": len(rows)}


@app.get("/api/v1/obstacles/{obstacle_id}/photo")
def obstacle_photo(obstacle_id: str):
    from fastapi.responses import FileResponse

    with DB_LOCK, db() as connection:
        row = connection.execute("SELECT photo_filename FROM obstacles WHERE id=?", (obstacle_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="obstacle not found")
    path = VOLUNTEER_UPLOAD_DIR / Path(row["photo_filename"]).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})


@app.get("/api/v1/volunteer/tasks/mine")
def my_volunteer_tasks(user: sqlite3.Row = Depends(current_user)) -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        rows = connection.execute(
            task_join_query("WHERE t.assignee_id=? ORDER BY t.updated_at DESC LIMIT 200"),
            (user["id"],),
        ).fetchall()
    return {"items": [task_payload(row) for row in rows], "count": len(rows)}


@app.get("/api/v1/volunteer/tasks")
def volunteer_tasks(
    status: Literal["open", "claimed", "submitted", "verified"] = Query(default="open"),
    _: sqlite3.Row = Depends(current_user),
) -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        rows = connection.execute(
            task_join_query(
                "WHERE t.status=? ORDER BY CASE t.priority WHEN 'urgent' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, t.created_at DESC LIMIT 300"
            ),
            (status,),
        ).fetchall()
    return {"items": [task_payload(row) for row in rows], "count": len(rows)}


@app.get("/api/v1/volunteer/tasks/{task_id}")
def volunteer_task_detail(task_id: str, _: sqlite3.Row = Depends(current_user)) -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        row = connection.execute(task_join_query("WHERE t.id=?"), (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"task": task_payload(row)}


@app.post("/api/v1/volunteer/tasks/{task_id}/claim")
def claim_volunteer_task(task_id: str, user: sqlite3.Row = Depends(current_user)) -> dict[str, Any]:
    timestamp = now_iso()
    with DB_LOCK, db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        cursor = connection.execute(
            "UPDATE public_tasks SET status='claimed',assignee_id=?,claimed_at=?,updated_at=? WHERE id=? AND status='open'",
            (user["id"], timestamp, timestamp, task_id),
        )
        if cursor.rowcount == 0:
            connection.rollback()
            if connection.execute("SELECT 1 FROM public_tasks WHERE id=?", (task_id,)).fetchone() is None:
                raise HTTPException(status_code=404, detail="task not found")
            raise HTTPException(status_code=409, detail="task has already been claimed")
        task = connection.execute("SELECT obstacle_id FROM public_tasks WHERE id=?", (task_id,)).fetchone()
        connection.execute("UPDATE obstacles SET status='assigned',updated_at=? WHERE id=?", (timestamp, task["obstacle_id"]))
        connection.execute(
            "UPDATE events SET status='dispatched',updated_at=? WHERE id=(SELECT event_id FROM obstacles WHERE id=?)",
            (timestamp, task["obstacle_id"]),
        )
        connection.execute(
            "INSERT INTO task_activity(task_id,actor_id,action,note,created_at) VALUES(?,?,?,'',?)",
            (task_id, user["id"], "claimed", timestamp),
        )
        connection.commit()
        row = connection.execute(task_join_query("WHERE t.id=?"), (task_id,)).fetchone()
    return {"task": task_payload(row)}


@app.post("/api/v1/volunteer/tasks/{task_id}/complete")
async def complete_volunteer_task(
    task_id: str,
    note: str = Form(...),
    photo: UploadFile = File(...),
    user: sqlite3.Row = Depends(current_user),
) -> dict[str, Any]:
    note = note.strip()
    if not 3 <= len(note) <= 500:
        raise HTTPException(status_code=422, detail="completion note must contain 3 to 500 characters")
    content = await photo.read(MAX_UPLOAD_BYTES + 1)
    filename = save_upload(photo, content, "completion")
    timestamp = now_iso()
    with DB_LOCK, db() as connection:
        task = connection.execute("SELECT * FROM public_tasks WHERE id=?", (task_id,)).fetchone()
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        if task["assignee_id"] != user["id"] or task["status"] != "claimed":
            raise HTTPException(status_code=409, detail="task is not claimable by the current user")
        connection.execute(
            "UPDATE public_tasks SET status='submitted',completion_note=?,completion_photo_filename=?,submitted_at=?,updated_at=? WHERE id=?",
            (note, filename, timestamp, timestamp, task_id),
        )
        obstacle = connection.execute("SELECT * FROM obstacles WHERE id=?", (task["obstacle_id"],)).fetchone()
        connection.execute("UPDATE obstacles SET status='resolving',updated_at=? WHERE id=?", (timestamp, obstacle["id"]))
        connection.execute("UPDATE events SET status='dispatched',updated_at=? WHERE id=?", (timestamp, obstacle["event_id"]))
        connection.execute(
            "INSERT INTO task_activity(task_id,actor_id,action,note,created_at) VALUES(?,?,?,?,?)",
            (task_id, user["id"], "submitted", note, timestamp),
        )
        connection.commit()
        row = connection.execute(task_join_query("WHERE t.id=?"), (task_id,)).fetchone()
    return {"task": task_payload(row)}


@app.get("/api/v1/admin/reports")
def admin_reports(status: Literal["pending", "approved", "rejected"] = Query(default="pending")) -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        rows = connection.execute(
            "SELECT r.*,u.email,u.display_name FROM volunteer_reports r JOIN users u ON u.id=r.reporter_id "
            "WHERE r.status=? ORDER BY r.created_at DESC LIMIT 300",
            (status,),
        ).fetchall()
        count_rows = connection.execute(
            "SELECT status,COUNT(*) AS count FROM volunteer_reports WHERE status<>'deleted' GROUP BY status"
        ).fetchall()
    items = []
    for row in rows:
        item = report_payload(row, "admin")
        item["reporter"] = {"email": row["email"], "displayName": row["display_name"]}
        items.append(item)
    counts = {"pending": 0, "approved": 0, "rejected": 0}
    counts.update({row["status"]: row["count"] for row in count_rows if row["status"] in counts})
    return {"items": items, "count": len(items), "counts": counts}


@app.get("/api/v1/admin/reports/{report_id}/photo")
def admin_report_photo(report_id: str):
    from fastapi.responses import FileResponse

    with DB_LOCK, db() as connection:
        row = connection.execute("SELECT photo_filename FROM volunteer_reports WHERE id=?", (report_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="report not found")
    path = VOLUNTEER_UPLOAD_DIR / Path(row["photo_filename"]).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="photo not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})


@app.patch("/api/v1/admin/reports/{report_id}")
def review_volunteer_report(report_id: str, review: AdminReportReview) -> dict[str, Any]:
    timestamp = now_iso()
    with DB_LOCK, db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        report = connection.execute("SELECT * FROM volunteer_reports WHERE id=?", (report_id,)).fetchone()
        if report is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="report not found")
        if report["status"] != "pending":
            connection.rollback()
            raise HTTPException(status_code=409, detail="report has already been reviewed")
        if review.action == "reject":
            if len(review.note.strip()) < 2:
                connection.rollback()
                raise HTTPException(status_code=422, detail="a rejection note is required")
            connection.execute(
                "UPDATE volunteer_reports SET status='rejected',priority=?,review_note=?,reviewed_by='operator',reviewed_at=?,updated_at=? WHERE id=?",
                (review.priority, review.note.strip(), timestamp, timestamp, report_id),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM volunteer_reports WHERE id=?", (report_id,)).fetchone()
            return {"report": report_payload(row, "admin"), "obstacle": None, "task": None}

        obstacle_id = f"OBS-{uuid.uuid4().hex[:10].upper()}"
        event_id = f"VB-VOL-{datetime.now(TZ).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        category_label = REPORT_CATEGORIES.get(report["category"], "其他障碍")
        photo_url = f"/api/v1/obstacles/{obstacle_id}/photo"
        connection.execute(
            "INSERT INTO events(id,source_event_id,device_id,type,type_label,status,severity,confidence,point_name,address,lat,lng,snapshot_url,source,created_at,updated_at,duration_sec) "
            "VALUES(?,?,?,?,?,'active',?,0,?,?,?,?,?,'志愿者审核入库',?,?,0)",
            (event_id, report_id, "volunteer-app", report["category"], category_label, PRIORITY_SEVERITY[review.priority], report["address"], report["address"], report["lat"], report["lng"], photo_url, report["created_at"], timestamp),
        )
        connection.execute(
            "INSERT INTO obstacles(id,report_id,event_id,category,category_label,description,address,lat,lng,photo_filename,priority,status,source,created_at,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,'open','volunteer',?,?)",
            (obstacle_id, report_id, event_id, report["category"], category_label, report["description"], report["address"], report["lat"], report["lng"], report["photo_filename"], review.priority, timestamp, timestamp),
        )
        connection.execute(
            "UPDATE volunteer_reports SET status='approved',priority=?,review_note=?,reviewed_by='operator',reviewed_at=?,obstacle_id=?,updated_at=? WHERE id=?",
            (review.priority, review.note.strip(), timestamp, obstacle_id, timestamp, report_id),
        )
        task_id = None
        if review.publish_task:
            task_id = f"VBT-{uuid.uuid4().hex[:10].upper()}"
            connection.execute(
                "INSERT INTO public_tasks(id,obstacle_id,title,description,priority,status,created_at,updated_at) VALUES(?,?,?,?,?,'open',?,?)",
                (task_id, obstacle_id, f"协助处理：{category_label}", report["description"], review.priority, timestamp, timestamp),
            )
            connection.execute(
                "INSERT INTO task_activity(task_id,actor_id,action,note,created_at) VALUES(?,NULL,'published',?,?)",
                (task_id, review.note.strip(), timestamp),
            )
        connection.commit()
        reviewed = connection.execute("SELECT * FROM volunteer_reports WHERE id=?", (report_id,)).fetchone()
        obstacle = connection.execute("SELECT * FROM obstacles WHERE id=?", (obstacle_id,)).fetchone()
        task = connection.execute(task_join_query("WHERE t.id=?"), (task_id,)).fetchone() if task_id else None
    return {
        "report": report_payload(reviewed, "admin"),
        "obstacle": obstacle_payload(obstacle),
        "task": task_payload(task) if task is not None else None,
    }


@app.get("/api/v1/admin/tasks")
def admin_tasks(status: str | None = Query(default=None)) -> dict[str, Any]:
    where = ""
    params: list[Any] = []
    if status:
        where = "WHERE t.status=? "
        params.append(status)
    where += "ORDER BY t.updated_at DESC LIMIT 500"
    with DB_LOCK, db() as connection:
        rows = connection.execute(task_join_query(where), params).fetchall()
        count_rows = connection.execute(
            "SELECT status,COUNT(*) AS count FROM public_tasks GROUP BY status"
        ).fetchall()
    counts = {"open": 0, "claimed": 0, "submitted": 0, "verified": 0, "cancelled": 0}
    counts.update({row["status"]: row["count"] for row in count_rows if row["status"] in counts})
    return {"items": [task_payload(row) for row in rows], "count": len(rows), "counts": counts}


@app.get("/api/v1/admin/operations/summary")
def admin_operations_summary() -> dict[str, Any]:
    """Return one authoritative snapshot for the volunteer dispatch pipeline."""
    expected = {
        "open": ("open", "active"),
        "claimed": ("assigned", "dispatched"),
        "submitted": ("resolving", "dispatched"),
        "verified": ("resolved", "cleared"),
        "cancelled": ("open", "active"),
    }
    with DB_LOCK, db() as connection:
        report_rows = connection.execute(
            "SELECT status,COUNT(*) AS count FROM volunteer_reports WHERE status<>'deleted' GROUP BY status"
        ).fetchall()
        task_rows = connection.execute(
            "SELECT status,COUNT(*) AS count FROM public_tasks GROUP BY status"
        ).fetchall()
        obstacle_rows = connection.execute(
            "SELECT status,COUNT(*) AS count FROM obstacles GROUP BY status"
        ).fetchall()
        state_rows = connection.execute(
            "SELECT t.id,t.status AS task_status,o.status AS obstacle_status,e.status AS event_status "
            "FROM public_tasks t JOIN obstacles o ON o.id=t.obstacle_id JOIN events e ON e.id=o.event_id"
        ).fetchall()
    issues = []
    for row in state_rows:
        wanted = expected.get(row["task_status"])
        if wanted and (row["obstacle_status"], row["event_status"]) != wanted:
            issues.append({
                "taskId": row["id"],
                "taskStatus": row["task_status"],
                "obstacleStatus": row["obstacle_status"],
                "eventStatus": row["event_status"],
                "expectedObstacleStatus": wanted[0],
                "expectedEventStatus": wanted[1],
            })
    return {
        "reports": {row["status"]: row["count"] for row in report_rows},
        "tasks": {row["status"]: row["count"] for row in task_rows},
        "obstacles": {row["status"]: row["count"] for row in obstacle_rows},
        "consistent": not issues,
        "issueCount": len(issues),
        "issues": issues[:50],
        "generatedAt": now_iso(),
    }


@app.get("/api/v1/admin/tasks/{task_id}/evidence")
def admin_task_evidence(task_id: str):
    from fastapi.responses import FileResponse

    with DB_LOCK, db() as connection:
        row = connection.execute("SELECT completion_photo_filename FROM public_tasks WHERE id=?", (task_id,)).fetchone()
    if row is None or not row["completion_photo_filename"]:
        raise HTTPException(status_code=404, detail="completion evidence not found")
    path = VOLUNTEER_UPLOAD_DIR / Path(row["completion_photo_filename"]).name
    if not path.exists():
        raise HTTPException(status_code=404, detail="completion evidence not found")
    return FileResponse(path, headers={"Cache-Control": "private, max-age=300"})


@app.patch("/api/v1/admin/tasks/{task_id}")
def review_volunteer_task(task_id: str, review: AdminTaskReview) -> dict[str, Any]:
    timestamp = now_iso()
    with DB_LOCK, db() as connection:
        connection.execute("BEGIN IMMEDIATE")
        task = connection.execute("SELECT * FROM public_tasks WHERE id=?", (task_id,)).fetchone()
        if task is None:
            connection.rollback()
            raise HTTPException(status_code=404, detail="task not found")
        obstacle = connection.execute("SELECT * FROM obstacles WHERE id=?", (task["obstacle_id"],)).fetchone()
        if review.action == "verify":
            if task["status"] != "submitted":
                connection.rollback()
                raise HTTPException(status_code=409, detail="only submitted tasks can be verified")
            connection.execute(
                "UPDATE public_tasks SET status='verified',review_note=?,verified_at=?,updated_at=? WHERE id=?",
                (review.note.strip(), timestamp, timestamp, task_id),
            )
            connection.execute("UPDATE obstacles SET status='resolved',resolved_at=?,updated_at=? WHERE id=?", (timestamp, timestamp, obstacle["id"]))
            connection.execute("UPDATE events SET status='cleared',updated_at=? WHERE id=?", (timestamp, obstacle["event_id"]))
            action = "verified"
        elif review.action == "return":
            if task["status"] != "submitted":
                connection.rollback()
                raise HTTPException(status_code=409, detail="only submitted tasks can be returned")
            if len(review.note.strip()) < 2:
                connection.rollback()
                raise HTTPException(status_code=422, detail="a return note is required")
            connection.execute(
                "UPDATE public_tasks SET status='claimed',review_note=?,submitted_at=NULL,updated_at=? WHERE id=?",
                (review.note.strip(), timestamp, task_id),
            )
            connection.execute("UPDATE obstacles SET status='assigned',updated_at=? WHERE id=?", (timestamp, obstacle["id"]))
            connection.execute("UPDATE events SET status='dispatched',updated_at=? WHERE id=?", (timestamp, obstacle["event_id"]))
            action = "returned"
        elif review.action == "cancel":
            if task["status"] == "verified":
                connection.rollback()
                raise HTTPException(status_code=409, detail="verified tasks cannot be cancelled")
            connection.execute(
                "UPDATE public_tasks SET status='cancelled',review_note=?,updated_at=? WHERE id=?",
                (review.note.strip(), timestamp, task_id),
            )
            connection.execute("UPDATE obstacles SET status='open',updated_at=? WHERE id=?", (timestamp, obstacle["id"]))
            connection.execute("UPDATE events SET status='active',updated_at=? WHERE id=?", (timestamp, obstacle["event_id"]))
            action = "cancelled"
        else:
            if task["status"] != "cancelled":
                connection.rollback()
                raise HTTPException(status_code=409, detail="only cancelled tasks can be reopened")
            connection.execute(
                "UPDATE public_tasks SET status='open',assignee_id=NULL,completion_note='',"
                "completion_photo_filename=NULL,review_note=?,claimed_at=NULL,submitted_at=NULL,verified_at=NULL,updated_at=? WHERE id=?",
                (review.note.strip(), timestamp, task_id),
            )
            connection.execute("UPDATE obstacles SET status='open',resolved_at=NULL,updated_at=? WHERE id=?", (timestamp, obstacle["id"]))
            connection.execute("UPDATE events SET status='active',updated_at=? WHERE id=?", (timestamp, obstacle["event_id"]))
            action = "reopened"
        connection.execute(
            "INSERT INTO task_activity(task_id,actor_id,action,note,created_at) VALUES(?,NULL,?,?,?)",
            (task_id, action, review.note.strip(), timestamp),
        )
        connection.commit()
        row = connection.execute(task_join_query("WHERE t.id=?"), (task_id,)).fetchone()
    return {"task": task_payload(row)}


@app.post("/api/v1/telemetry", status_code=202)
def ingest_telemetry(payload: TelemetryEnvelope, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    provided = (authorization or "").removeprefix("Bearer ").strip()
    if not INGEST_TOKEN or not hmac.compare_digest(provided, INGEST_TOKEN):
        raise HTTPException(status_code=401, detail="invalid ingest token")
    body = payload.dict()
    device_id = str(payload.device.get("device_id") or payload.device.get("gateway_id") or "unknown-device")
    point_name = str(payload.device.get("point_name") or "blindway-point-01")
    received = now_iso()
    snapshot_url = None
    if payload.snapshot_b64 and payload.snapshot_filename:
        safe_name = f"{uuid.uuid4().hex[:10]}-{Path(payload.snapshot_filename).name}"
        try:
            decoded = base64.b64decode(payload.snapshot_b64, validate=True)
            if len(decoded) <= 4 * 1024 * 1024:
                (SNAPSHOT_DIR / safe_name).write_bytes(decoded)
                snapshot_url = f"/api/v1/snapshots/{safe_name}"
        except (ValueError, base64.binascii.Error):
            pass
    with DB_LOCK, db() as connection:
        existing_device = connection.execute("SELECT name FROM devices WHERE device_id=?", (device_id,)).fetchone()
        device_name = str(
            payload.device.get("name")
            or (existing_device["name"] if existing_device else "")
            or default_device_name(device_id)
        )
        connection.execute(
            "INSERT INTO telemetry(device_id,received_at,source_ts,payload) VALUES (?,?,?,?)",
            (device_id, received, payload.ts or received, json.dumps(body, ensure_ascii=False, separators=(",", ":"))),
        )
        connection.execute(
            "INSERT INTO devices(device_id,name,point_name,last_seen,status,payload) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(device_id) DO UPDATE SET name=excluded.name,point_name=excluded.point_name,last_seen=excluded.last_seen,status=excluded.status,payload=excluded.payload",
            (device_id, device_name, point_name, received, "online", json.dumps(body, ensure_ascii=False, separators=(",", ":"))),
        )
        props = payload.iot_properties
        runtime = payload.runtime
        if int(props.get("eventActive", 0)) == 1:
            source_event_id = str(runtime.get("last_event_id") or f"{device_id}-{props.get('captureEpoch', 0)}")
            event_type = str(runtime.get("last_obstacle_type") or "construction_obstacle")
            confidence = int(runtime.get("last_confidence") or props.get("obstacleConfidence", 0))
            lat = float(payload.gps.get("lat") or props.get("gpsLatE6", 0) / 1_000_000 or DEFAULT_LAT)
            lng = float(payload.gps.get("lng") or props.get("gpsLngE6", 0) / 1_000_000 or DEFAULT_LNG)
            event_id = f"VB-{parse_time(payload.ts).strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
            created = parse_time(payload.ts).isoformat(timespec="seconds")
            connection.execute(
                "INSERT INTO events(id,source_event_id,device_id,type,type_label,status,severity,confidence,point_name,address,lat,lng,snapshot_url,source,created_at,updated_at,duration_sec) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(source_event_id) DO UPDATE SET confidence=excluded.confidence,updated_at=excluded.updated_at,duration_sec=CAST((julianday(excluded.updated_at)-julianday(events.created_at))*86400 AS INTEGER),snapshot_url=COALESCE(excluded.snapshot_url,events.snapshot_url)",
                (event_id, source_event_id, device_id, event_type, event_label(event_type), "active", severity_for(int(props.get("alertLevelCode", 0)), confidence), point_name, "移动巡检终端实时上报点位", lat, lng, snapshot_url, "树莓派实机", created, received, 0),
            )
        connection.execute("DELETE FROM telemetry WHERE id NOT IN (SELECT id FROM telemetry ORDER BY id DESC LIMIT 50000)")
        connection.commit()
    return {"accepted": True, "deviceId": device_id, "receivedAt": received}


@app.get("/api/v1/overview")
def overview() -> dict[str, Any]:
    paths = media_paths()
    with DB_LOCK, db() as connection:
        device_rows = connection.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
        device_row = device_rows[0] if device_rows else None
        events = [row_to_event(row) for row in connection.execute(
            "SELECT * FROM events WHERE status IN ('active','dispatched') ORDER BY created_at DESC LIMIT 20"
        ).fetchall()]
        devices = [normalize_device(row, paths) for row in device_rows]
        device = devices[0] if devices else normalize_device(None, paths)
        online_devices = sum(1 for item in devices if item["status"] == "online")
        live = online_devices > 0
        today_prefix = datetime.now(TZ).date().isoformat()
        today_count = connection.execute("SELECT COUNT(*) FROM events WHERE created_at LIKE ?", (today_prefix + "%",)).fetchone()[0]
        total = connection.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        cleared = connection.execute("SELECT COUNT(*) FROM events WHERE status='cleared'").fetchone()[0]
        active = connection.execute("SELECT COUNT(*) FROM events WHERE status IN ('active','dispatched')").fetchone()[0]
        demo_count = connection.execute("SELECT COUNT(*) FROM events WHERE source='历史演示样例'").fetchone()[0]
    labels = ["08", "10", "12", "14", "16", "18", "20", "22"]
    return {
        "generatedAt": now_iso(),
        "dataMode": "hybrid" if live and demo_count else "live" if live else "demo",
        "linkStatus": "online" if live else "offline",
        "kpis": {
            "onlineDevices": online_devices, "totalDevices": max(1, len(devices)),
            "activeEvents": active, "todayEvents": today_count,
            "closureRate": round(cleared / total * 100) if total else 0,
            "averageResponseMin": 4.8,
        },
        "device": device,
        "recentEvents": events,
        "trends": {"labels": labels, "events": [1,2,1,4,3,5,3,2], "inferenceMs": [708,692,681,674,666,672,658,664], "cameraFps": [7.2,7.4,7.7,7.8,7.6,7.8,7.9,7.8]},
    }


@app.get("/api/v1/events")
def list_events(status: str | None = Query(default=None), limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    query = "SELECT * FROM events"
    params: list[Any] = []
    if status:
        query += " WHERE status=?"
        params.append(status)
    else:
        query += " WHERE status IN ('active','dispatched')"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    with DB_LOCK, db() as connection:
        rows = connection.execute(query, params).fetchall()
    return {"items": [row_to_event(row) for row in rows], "count": len(rows)}


@app.patch("/api/v1/events/{event_id}")
def update_event(event_id: str, action: EventAction) -> dict[str, Any]:
    status = "dispatched" if action.action == "dispatch" else "cleared"
    with DB_LOCK, db() as connection:
        volunteer_obstacle = connection.execute(
            "SELECT 1 FROM obstacles WHERE event_id=? AND source='volunteer'", (event_id,)
        ).fetchone()
        if volunteer_obstacle is not None:
            raise HTTPException(
                status_code=409,
                detail="volunteer events must be closed through task verification",
            )
        cursor = connection.execute("UPDATE events SET status=?,updated_at=? WHERE id=?", (status, now_iso(), event_id))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="event not found")
        connection.commit()
        row = connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
    return row_to_event(row)


@app.get("/api/v1/devices")
def list_devices() -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        rows = connection.execute("SELECT * FROM devices ORDER BY last_seen DESC").fetchall()
    paths = media_paths()
    return {"items": [normalize_device(row, paths) for row in rows], "count": len(rows), "generatedAt": now_iso()}


@app.get("/api/v1/devices/{device_id}")
def get_device(device_id: str) -> dict[str, Any]:
    with DB_LOCK, db() as connection:
        row = connection.execute("SELECT * FROM devices WHERE device_id=?", (device_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="device not found")
    return normalize_device(row, media_paths())


@app.get("/api/v1/snapshots/{filename}")
def snapshot_metadata(filename: str):
    from fastapi.responses import FileResponse
    safe = Path(filename).name
    path = SNAPSHOT_DIR / safe
    if not path.exists():
        raise HTTPException(status_code=404, detail="snapshot not found")
    return FileResponse(path, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=300"})


@app.websocket("/ws/realtime")
async def realtime(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"type": "heartbeat", "time": now_iso()})
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        return


if os.getenv("VISIONBRIDGE_SERVE_STATIC", "0") == "1":
    from fastapi.staticfiles import StaticFiles

    dashboard_static = BASE_DIR.parent / "static-deploy"
    volunteer_static = BASE_DIR.parent.parent / "volunteer-app" / "build" / "web"
    if volunteer_static.exists():
        app.mount("/volunteer", StaticFiles(directory=volunteer_static, html=True), name="volunteer-app")
    if dashboard_static.exists():
        app.mount("/", StaticFiles(directory=dashboard_static, html=True), name="dashboard")
