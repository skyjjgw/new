# 志愿者 App

Flutter 客户端支持 QQ 邮箱验证码登录、障碍地图、拍照上报、系统定位与地图选点、地图/任务列表接单、处理凭证提交和个人记录管理。

## 运行

```bash
flutter pub get
flutter run --dart-define=VISIONBRIDGE_API_BASE=http://127.0.0.1:8000
```

Android 真机需要使用手机可访问的局域网地址或 HTTPS 域名。Web 同源部署使用：

```bash
flutter build web --release \
  --base-href /volunteer/ \
  --dart-define=VISIONBRIDGE_API_BASE=same-origin
```

Android 发布构建：

```bash
flutter build apk --release \
  --dart-define=VISIONBRIDGE_API_BASE=https://your-domain.example
```

正式分发前必须配置独立 release keystore、HTTPS、高德地图域名白名单和隐私说明。SMTP 授权码只属于服务端，绝不能放入 App。

## 地图与定位

高德地图 JS Key 和安全密钥由自有云公开配置接口下发；手机位置由系统定位服务产生，服务器只接收业务坐标。地图加载失败时保留降级选点界面，定位质量受权限、卫星/网络环境和采样窗口影响。

## 验证

```bash
flutter analyze
flutter test
```
