# 边缘端

`pi-runtime/` 是当前活动链路：USB 摄像头采集、LC76G GNSS、YOLOv8 ONNX 推理、事件生成、遥测直传和标注视频发布都在边缘设备完成。

## 目录

- `visionbridge_edge_agent.py`：采集、推理、事件状态机、HTTP 遥测和本地预览；
- `run_visionbridge_edge.sh`：读取 `/etc/visionbridge/edge.env` 并启动 Agent；
- `visionbridge-edge-agent.service`：主进程 systemd 服务；
- `run_visionbridge_media_publisher.sh`：FFmpeg 编码和 RTSP 发布；
- `visionbridge-media-*.service`：SSH 媒体隧道和发布服务；
- `models/README.md`：模型发布与本地放置规则。

## 部署概要

1. 安装 Python、OpenCV、NumPy、PySerial、pynmea2、Flask、FFmpeg 和摄像头/GNSS 依赖；
2. 将本目录安装到 `/opt/visionbridge/edge`；
3. 将 `visionbridge_edge.env.example` 复制到 `/etc/visionbridge/edge.env`；
4. 放置经过验证的模型并设置 `MODEL_PATH`；
5. 运行 `install_visionbridge_edge_service.sh`；
6. 检查 `visionbridge-edge-agent.service`，再启用媒体隧道与发布服务。

真实上传令牌和媒体密钥只能保存在设备权限受限的环境文件中。低延迟参数和实机数据见 [性能记录](性能优化与低延迟链路说明_20260803.md)。
