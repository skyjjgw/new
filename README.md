# VisionBridge AIoT Accessibility（视桥）

视桥是一套面向城市盲道和无障碍通行的边云协同平台：边缘设备在本地完成障碍识别与定位，自有云统一管理设备、事件、地图和实时视频，Flutter 志愿者 App 负责拍照上报、公共接单、现场处置与复核闭环。

## 功能概览

- 树莓派/边缘终端运行 YOLOv8 ONNX，本地完成识别和事件生成；
- 设备遥测和障碍数据直传自有云，不依赖第三方 IoT 平台；
- 管理大屏提供实时地图、审核派单、设备健康和多设备视频入口；
- MediaMTX + WebRTC/WHEP 提供低延迟画面，coturn 负责 NAT 中继；
- Flutter App 支持邮箱验证码登录、拍照上报、地图选点、接单和闭环反馈；
- App 与云端通过短轮询和操作后刷新保持状态一致。

## 仓库结构

```text
visionbridge-aiot-accessibility/
├─ .github/workflows/       # GitHub Actions
├─ apps/
│  ├─ dashboard/            # React/Vinext 管理大屏 + FastAPI 服务
│  └─ volunteer/            # Flutter 志愿者 App
├─ edge/
│  └─ pi-runtime/           # 摄像头、GNSS、ONNX 推理、直传与视频发布
├─ deploy/                  # 云服务器发布、MediaMTX 与 coturn 部署工具
├─ integrations/
│  └─ advantech-iotsuite/   # 研华 IoTSuite 历史兼容与参考代码
├─ docs/                    # 架构、需求、赛事、硬件与答辩资料
├─ assets/                  # 项目图片、图形和展示素材
├─ SECURITY.md
└─ README.md
```


## 快速开始

### 1. 管理大屏

要求 Node.js 22.13 或更高版本。

```bash
cd apps/dashboard
npm ci
npm run dev
```

### 2. 自有云 API

```bash
cd apps/dashboard
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
uvicorn server.app:app --reload --port 8000
```

启动前请把 `.env` 中的占位值替换为本地开发值。不要修改并提交 `.env.example` 来保存真实凭据。

### 3. 志愿者 App

```bash
cd apps/volunteer
flutter pub get
flutter run --dart-define=VISIONBRIDGE_API_BASE=http://127.0.0.1:8000
```

Android 真机访问电脑服务时，应将 API 地址换成手机可访问的局域网或 HTTPS 域名。

### 4. 边缘端

```bash
cd edge/pi-runtime
cp visionbridge_edge.env.example /etc/visionbridge/edge.env
cp visionbridge_media.env.example /etc/visionbridge/media-publisher.env
```

填写真实自有云地址和随机令牌后，按 [边缘端部署说明](edge/README.md) 安装 systemd 服务。真实配置只保存在设备或服务器上。

## 验证

```bash
cd apps/dashboard
npm test
python -m pytest server/test_volunteer_api.py

cd ../volunteer
flutter test
```

## 文档

- [完整使用与部署说明](docs/USAGE.md)
- [项目需求与接口设计](docs/design/视桥_云端可视化平台_需求规格与接口设计.md)
- [边缘性能与低延迟链路](edge/性能优化与低延迟链路说明_20260803.md)
- [安全与密钥规范](SECURITY.md)
- [贡献指南](CONTRIBUTING.md)

## 仓库名称

`visionbridge-aiot-accessibility` 同时表达品牌“视桥”、AIoT 边云协同能力和无障碍应用场景，比临时名称 `new` 更适合长期维护与展示。

----
