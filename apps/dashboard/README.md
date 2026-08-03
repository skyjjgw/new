# 视桥管理大屏与自有云 API

该应用包含两个可独立运行的部分：

- `app/`：React + Vinext 管理大屏；
- `server/`：FastAPI + SQLite 自有云 API。

管理大屏覆盖事件地图、设备健康、多设备实时视频、志愿者上报审核和公共派单。API 为边缘端、大屏与志愿者 App 提供统一数据源。

## 前端开发

```bash
npm ci
npm run dev
```

常用命令：

```bash
npm run lint
npm test
npm run export:static
```

## API 开发

```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1
# Linux/macOS: source .venv/bin/activate
pip install -r server/requirements.txt
cp .env.example .env
uvicorn server.app:app --reload --port 8000
```

`.env.example` 只包含无效占位值。生产环境必须重新生成认证密钥、设备上传令牌、SMTP 授权码和地图服务配置。

## 测试

```bash
npm test
python -m pytest server/test_volunteer_api.py
```

需求、字段与验收标准见 [云端需求规格与接口设计](../../docs/design/视桥_云端可视化平台_需求规格与接口设计.md)。

