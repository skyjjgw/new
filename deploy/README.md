# 部署工具

- `deploy_release.py`：上传经过验证的发布包，并在服务器端执行健康检查和失败回滚；
- `deploy_media_stack.py`：安装/更新 MediaMTX、coturn，并连接边缘端视频发布链路；
- `mediamtx-release.json`：MediaMTX 版本与发布信息；
- `visionbridge-release-*.tar.gz`、`release-staging-*`：本地产物，已被 Git 忽略。

部署脚本从进程环境读取凭据：

```powershell
$env:VISIONBRIDGE_SSH_PASSWORD = '<cloud-password>'
$env:VISIONBRIDGE_PI_PASSWORD = '<edge-password>'
python deploy\deploy_media_stack.py
```

不要把上面的占位值替换后写入脚本、README 或 shell 历史。生产部署应优先使用 SSH 密钥和受限部署账户。

