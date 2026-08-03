# 视桥志愿者 App

Flutter 客户端支持邮箱验证码登录、障碍地图、拍照上报、地图选点、公共任务接单、处理凭证提交和个人记录管理。

## 运行

```bash
flutter pub get
flutter run --dart-define=VISIONBRIDGE_API_BASE=http://127.0.0.1:8000
```

Android 真机不能使用电脑的 `127.0.0.1`，请替换为手机可访问的局域网地址或 HTTPS 域名。

## Web 构建

```bash
flutter build web --release \
  --base-href /volunteer/ \
  --dart-define=VISIONBRIDGE_API_BASE=same-origin
```

## Android 构建

```bash
flutter build apk --release \
  --dart-define=VISIONBRIDGE_API_BASE=https://your-domain.example
```

正式分发前必须配置项目自己的 release keystore 和 HTTPS 域名。App 不保存 SMTP 授权码，验证码只能由自有云发送。

## 地图与定位

高德地图配置由自有云公开配置接口下发；定位由设备系统服务提供，服务器只负责接收坐标和返回业务数据。若地图不可用，App 会显示可手动选点的降级界面。

## 验证

```bash
flutter analyze
flutter test
```

