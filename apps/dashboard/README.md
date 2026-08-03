# 管理大屏

React + TypeScript 管理端，提供事件地图、志愿者上报审核、公共派单、设备健康、多设备选择和 WebRTC/HLS 视频播放。

## 开发

```bash
npm ci
npm run dev
```

开发服务器需要将 `/api` 代理到 `services/api` 的本地端口。生产环境通过 Nginx 同源托管静态文件、API 与媒体路径。

## 命令

```bash
npm run lint
npm test
npm run export:static
```

配置契约见 `.env.example`，真实环境变量不得进入仓库。业务字段见 [API 概览](../../docs/API.md)。
