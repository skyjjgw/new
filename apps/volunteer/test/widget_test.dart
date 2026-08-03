import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:visionbridge_volunteer/api_client.dart';
import 'package:visionbridge_volunteer/screens/auth_screen.dart';
import 'package:visionbridge_volunteer/screens/home_shell.dart';
import 'package:visionbridge_volunteer/screens/privacy_screen.dart';

void main() {
  testWidgets('single-character nickname can complete first login',
      (tester) async {
    var authenticated = false;
    final client = MockClient((request) async {
      if (request.url.path.endsWith('/request')) {
        return http.Response(
            '{"sent":true,"expiresIn":600,"debugCode":"123456"}', 200,
            headers: {'content-type': 'application/json'});
      }
      if (request.url.path.endsWith('/verify')) {
        expect(request.body, contains('"displayName":"1"'));
        return http.Response(
            '{"token":"token","user":{"id":"USR-1","email":"tester@example.com","displayName":"1","role":"volunteer"}}',
            200,
            headers: {'content-type': 'application/json'});
      }
      return http.Response('{"detail":"not found"}', 404);
    });
    await tester.pumpWidget(MaterialApp(
        home: AuthScreen(
            api: ApiClient(baseUrl: 'http://test', client: client),
            onAuthenticated: (_) async => authenticated = true)));

    await tester.enterText(
        find.widgetWithText(TextField, '邮箱地址'), 'tester@example.com');
    await tester.tap(find.text('获取邮箱验证码'));
    await tester.pumpAndSettle();
    await tester.enterText(find.widgetWithText(TextField, '志愿者昵称（可留空）'), '1');
    await tester.tap(find.text('验证并登录'));
    await tester.pumpAndSettle();
    expect(authenticated, isTrue);
    expect(find.textContaining('ensure this value'), findsNothing);
  });

  testWidgets('privacy gate explains permissions before continuing',
      (tester) async {
    var accepted = false;
    await tester
        .pumpWidget(MaterialApp(home: PrivacyScreen(onAccepted: () async {
      accepted = true;
    })));

    expect(find.text('一起把每一段盲道\n变得更安全'), findsOneWidget);
    expect(find.text('相机与相册'), findsOneWidget);
    expect(find.text('定位与高德地图'), findsOneWidget);
    expect(find.text('邮箱验证'), findsOneWidget);

    await tester.scrollUntilVisible(find.text('同意并继续'), 180,
        scrollable: find.byType(Scrollable));
    await tester.pumpAndSettle();
    final continueButton =
        tester.widget<FilledButton>(find.widgetWithText(FilledButton, '同意并继续'));
    expect(continueButton.onPressed, isNull);

    await tester.tap(find.byType(Checkbox));
    await tester.pump();
    await tester.tap(find.widgetWithText(FilledButton, '同意并继续'));
    await tester.pump();
    expect(accepted, isTrue);
  });

  testWidgets('home shell exposes map report task and profile navigation',
      (tester) async {
    final client = MockClient((request) async {
      final path = request.url.path;
      if (path == '/api/v1/config/public') {
        return http.Response(
            '{"amapKey":"","defaultCenter":[121.138923,28.632112]}', 200,
            headers: {'content-type': 'application/json'});
      }
      if (path == '/api/v1/map/obstacles') {
        return http.Response(
            '{"items":[{"id":"OBS-1","categoryLabel":"路面坑洼/破损","description":"测试障碍","address":"学院路","lat":28.632112,"lng":121.138923,"photoUrl":"/photo","priority":"urgent","status":"open"}]}',
            200,
            headers: {'content-type': 'application/json'});
      }
      if (path == '/api/v1/auth/me') {
        return http.Response(
            '{"user":{"id":"USR-1","email":"tester@example.com","displayName":"测试志愿者","role":"volunteer"}}',
            200,
            headers: {'content-type': 'application/json'});
      }
      if (path.contains('/volunteer/tasks') ||
          path.contains('/volunteer/reports')) {
        return http.Response('{"items":[]}', 200,
            headers: {'content-type': 'application/json'});
      }
      return http.Response('{"detail":"not found"}', 404,
          headers: {'content-type': 'application/json'});
    });
    final api = ApiClient(baseUrl: 'http://test', client: client)
      ..token = 'test';

    await tester.pumpWidget(
        MaterialApp(home: HomeShell(api: api, onLogout: () async {})));
    await tester.pumpAndSettle();

    expect(find.text('障碍物地图'), findsOneWidget);
    expect(find.text('地图标注'), findsOneWidget);
    expect(find.text('地图'), findsOneWidget);
    expect(find.text('上报'), findsOneWidget);
    expect(find.text('任务'), findsOneWidget);
    expect(find.text('我的'), findsOneWidget);

    await tester.tap(find.text('任务'));
    await tester.pumpAndSettle();
    expect(find.text('公共派单'), findsOneWidget);
  });
}
