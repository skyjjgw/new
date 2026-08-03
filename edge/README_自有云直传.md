# 视桥边缘端：自有云直传说明

## 当前唯一运行链路

```mermaid
flowchart LR
    Camera[USB 摄像头] --> Edge[树莓派视觉主进程]
    GPS[LC76G GNSS] --> Edge
    Edge -->|REST JSON + Bearer Token\n5 秒心跳 / 事件即时| API[视桥自有云 API]
    API --> DB[(SQLite)]
    DB --> Web[可视化网站]
```

- 主程序：`pi-runtime/visionbridge_edge_agent.py`，不连接 IoTSuite、DCCS 或 MQTT。
- 启动脚本：`pi-runtime/run_visionbridge_edge.sh`。
- systemd：`visionbridge-edge-agent.service`。
- 传输目标：`VISIONBRIDGE_CLOUD_URL`，当前为自有云 `/api/v1/telemetry`。
- 鉴权：`VISIONBRIDGE_INGEST_TOKEN`，仅放入树莓派权限受限的环境文件，不写入源码。
- 可靠性：上传在线程内执行，失败指数退避重试；视觉推理线程不等待网络。
- 事件：首次进入 active 时立即上传状态与抓拍；普通设备状态按 `HEARTBEAT_INTERVAL` 上传。

## 已停用内容

- 研华 DCCS 服务凭据获取。
- 研华 MQTT report/heartbeat 发布。
- 研华工作流运行配置。
- 独立轮询型 `visionbridge-cloud-bridge.service`（实机已 inactive / disabled）。

## 必需环境变量

参见 `pi-runtime/visionbridge_edge.env.example`。部署文件为 `/etc/visionbridge/edge.env`，权限不高于 `0640`。
