# 应用

- `dashboard/`：React/Vinext 管理大屏，以及 `server/` 下的 FastAPI 服务；
- `volunteer/`：面向志愿者的 Flutter Android/Web/Windows 客户端。

两个应用共享自有云 API 契约。修改状态字段、认证方式或地图数据结构时，需要同步验证两端。

