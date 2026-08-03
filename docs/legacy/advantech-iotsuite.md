# 研华 IoTSuite 历史兼容说明

项目早期通过研华 IoTSuite、DCCS/MQTT 和轮询桥接上传设备数据。当前架构已经改为边缘设备直接调用视桥自有云 `POST /api/v1/telemetry`，实时视频也直接发布到自有 MediaMTX/coturn，不再依赖第三方业务平台。

为避免读者误用旧传输方式，历史适配源码和厂商文档没有进入公开主分支，保存在本地历史区。若比赛答辩需要说明演进过程，可以使用以下表述：

| 阶段 | 数据路径 | 当前状态 |
| --- | --- | --- |
| 早期验证 | Edge → IoTSuite/DCCS/MQTT → 桥接服务 | 已停用 |
| 当前版本 | Edge → VisionBridge 自有云 API | 唯一生产链路 |
| 实时视频 | Edge FFmpeg → MediaMTX/coturn → Dashboard | 当前链路 |

代码中不应再出现 `IOTSUITE_*` 配置兼容项或以 `iotsuite` 命名的活动服务。
