# 自有云 API

FastAPI + SQLite 业务服务，是设备、事件、地图、志愿者上报和公共任务的唯一事实源。

## 运行

从仓库根目录执行：

```bash
python -m venv .venv
pip install -r services/api/requirements.txt
uvicorn services.api.app:app --reload --port 8000
```

本地环境变量可参考 `apps/dashboard/.env.example`。生产环境必须关闭调试验证码和演示数据，并由 Nginx 或独立身份网关保护管理接口。

## 测试

```bash
python -m pytest services/api/test_volunteer_api.py
```

接口列表见 [docs/API.md](../../docs/API.md)，数据和状态流见 [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md)。
