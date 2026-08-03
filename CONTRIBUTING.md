# 贡献指南

## 开发流程

1. 从 `main` 创建短生命周期分支；
2. 变更前阅读 [仓库内容策略](docs/REPOSITORY_POLICY.md)，不要提交凭据、数据库、用户图片、模型、安装包或构建产物；
3. 修改接口时同步更新 API 测试、Dashboard、Flutter 模型和 `docs/API.md`；
4. 提交前运行受影响模块的 lint、测试和构建；
5. Pull Request 说明问题、方案、验证证据、风险和回滚方式；
6. 使用 `feat:`、`fix:`、`docs:`、`refactor:`、`test:`、`build:` 或 `chore:` 等清晰提交前缀。

## 完成标准

- Dashboard 可构建，相关渲染测试通过；
- API 业务流程测试通过，状态迁移和权限边界有覆盖；
- Flutter 通过 `flutter analyze` 和 `flutter test`；
- 边缘改动通过语法检查，并记录摄像头/GNSS/模型实机验证；
- 新增配置已进入 `*.env.example`，且示例值无效；
- 用户可见行为、接口或部署变化已更新文档；
- 没有新增大文件、真实凭据、生产数据或版权不明确的素材。

## 二进制和模型

模型、APK、PPT、演示视频和发布压缩包不直接提交到 Git。需要发布时使用带版本标签的 GitHub Release，并附 SHA-256、来源、许可证和兼容性说明。
