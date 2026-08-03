# 用户应用

- `dashboard/`：React/TypeScript 管理大屏，消费自有云 API 与 WebRTC/HLS 媒体服务；
- `volunteer/`：Flutter Android/Web 客户端，覆盖邮箱登录、上报、地图、任务和个人记录。

业务 API 位于 `../services/api/`。修改接口字段或状态机时，必须同步更新两个应用及 `docs/API.md`。
