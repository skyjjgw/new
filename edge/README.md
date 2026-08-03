# 边缘端

`pi-runtime/` 是当前生产链路：摄像头采集、GNSS 定位、YOLOv8 ONNX 推理、事件直传和视频发布均在边缘设备完成。

## 部署概要

1. 安装 Python、OpenCV、ONNX Runtime、FFmpeg 和摄像头/GNSS 依赖；
2. 将 `visionbridge_edge.env.example` 与 `visionbridge_media.env.example` 复制到 `/etc/visionbridge/`；
3. 填写设备 ID、自有云地址、上传令牌与媒体发布密钥；
4. 使用 `install_blind_occupancy_service.sh` 安装识别服务；
5. 启用 `visionbridge-media-publisher.service` 后检查服务日志和云端设备状态。

详细参数和低延迟调优见 [性能优化与低延迟链路说明_20260803.md](性能优化与低延迟链路说明_20260803.md)。

