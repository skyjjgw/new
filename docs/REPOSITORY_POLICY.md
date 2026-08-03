# 仓库内容与大文件策略

## 1. 目标

Git 仓库用于保存可审查、可复现、会随代码共同演进的文本和必要小型资源。运行数据、凭据、可重新构建的产物、训练权重和展示交付物不应混入主分支历史。

本策略参考：

- [GitHub README 官方说明](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)
- [GitHub Releases 官方说明](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)
- [Git Large File Storage 官方说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage)
- [GitHub 仓库安全快速入门](https://docs.github.com/en/code-security/getting-started/quickstart-for-securing-your-repository)
- [FastAPI 官方全栈模板](https://github.com/fastapi/full-stack-fastapi-template)
- [Flutter 官方 samples 仓库](https://github.com/flutter/samples)
- [MediaMTX 官方仓库](https://github.com/bluenviron/mediamtx)

## 2. 应提交到 Git

| 内容 | 原因 |
| --- | --- |
| 应用、API、边缘端源码 | 可审查、可测试、需要版本历史 |
| `package-lock.json`、`pubspec.lock` | 保证应用构建可复现 |
| 测试、CI、lint 和格式配置 | 保证质量门禁一致 |
| `*.env.example` | 记录配置契约，示例必须是无效占位值 |
| Nginx、systemd、MediaMTX、coturn 模板 | 部署定义应与代码共同评审 |
| Markdown 架构、接口、开发和部署文档 | 帮助使用与维护 |
| README 使用的少量压缩截图/SVG | 直接支持项目理解 |
| 数据库 schema 或迁移文件 | 保证数据结构可重建 |

## 3. 不应提交到 Git

| 内容 | 去向 |
| --- | --- |
| `.env`、授权码、Token、SSH 私钥、证书私钥 | 本地密钥存储、服务器 Secret 或 CI Secrets |
| SQLite 数据库、用户图片、快照、日志 | 服务器持久卷与备份系统 |
| `node_modules`、`.dart_tool`、`.venv`、构建缓存 | 由包管理器重新生成 |
| `dist`、`.next`、Flutter `build`、APK/AAB | CI 构建；需要分发时放 Release |
| ONNX/TFLite/PT 模型权重 | GitHub Release、模型仓库或对象存储 |
| 最终 PPT、演示视频、发布压缩包 | GitHub Release 或赛事提交盘 |
| 赛事官方 PDF、厂商原始文档 | 保留官方链接；无再分发授权时不上传 |
| 数据集、训练图片、原始素材与批量抠图 | 数据集/对象存储；仓库仅放许可与索引 |
| `.trae`、`90_历史版本与过程文件`、`99_私密配置_禁止提交` | 仅本地工作区 |
| 真实服务器 IP 清单、故障记录和备份脚本输出 | 私有运维记录 |

## 4. Git LFS 与 Releases 的选择

- 源码运行时每次克隆都必须取得、且需要与提交严格绑定的大型二进制，可考虑 Git LFS；
- APK、PPT、视频、模型权重和发布压缩包更适合作为带版本标签的 GitHub Release 资产；
- 训练数据和持续增长的用户数据不适合 Git LFS，应使用数据集平台或对象存储；
- 使用 LFS 前需要确认团队成员安装、存储与带宽配额，以及 Fork 的使用成本。

本项目当前选择：主分支不跟踪模型、PPT、APK、赛事 PDF 和原始素材；以后发布时将模型和成品放入 Release，并附 SHA-256、模型输入尺寸、类别和许可证信息。

## 5. 提交前检查

```bash
git status --short
git diff --check
git ls-files | sort
git grep -n -I -E "(PASSWORD|SECRET|AUTH_CODE|API_KEY|TOKEN)"
```

字符串扫描只能发现明显风险，不能替代 GitHub Secret Scanning、push protection 和人工检查。发现真实凭据进入提交历史时，应先轮换凭据，再评估是否重写历史。

## 6. 当前本地归档

本次整理移出的模型、PPT、比赛手册、原始素材、旧 IoTSuite 适配和部署验证记录保存在本地 `90_历史版本与过程文件/github-excluded-20260803/`。该目录被 `.gitignore` 整体排除，不会随仓库上传。
