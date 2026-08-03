# 部署资源

```text
deploy/
├─ coturn/          # TURN 配置模板
├─ mediamtx/        # MediaMTX 配置与版本元数据
├─ nginx/           # 网站、API 和媒体反向代理
├─ systemd/         # 云端服务单元
└─ scripts/         # 单节点发布与媒体栈部署脚本
```

脚本从环境变量读取目标主机和凭据：

```powershell
$env:VISIONBRIDGE_CLOUD_HOST = 'cloud.example.com'
$env:VISIONBRIDGE_EDGE_HOST = '192.0.2.10'
$env:VISIONBRIDGE_CLOUD_USER = 'root'
$env:VISIONBRIDGE_SSH_PASSWORD = '<cloud-password>'
$env:VISIONBRIDGE_PI_PASSWORD = '<edge-password>'
python deploy\scripts\deploy_media_stack.py
```

生产环境优先使用 SSH 密钥、受限部署账户和固定 host key；密码环境变量仅保留给当前原型脚本。不要把真实值写入 README、脚本、命令历史或 GitHub Actions 日志。

完整端口、发布、回滚与验收规则见 [部署指南](../docs/DEPLOYMENT.md)。
