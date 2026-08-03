import 'package:flutter/material.dart';

import 'api_client.dart';
import 'app_theme.dart';
import 'screens/auth_screen.dart';
import 'screens/home_shell.dart';
import 'screens/privacy_screen.dart';
import 'session_store.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const VisionBridgeVolunteerApp());
}

class VisionBridgeVolunteerApp extends StatefulWidget {
  const VisionBridgeVolunteerApp(
      {super.key, this.apiClient, this.sessionStore});
  final ApiClient? apiClient;
  final SessionStore? sessionStore;

  @override
  State<VisionBridgeVolunteerApp> createState() =>
      _VisionBridgeVolunteerAppState();
}

class _VisionBridgeVolunteerAppState extends State<VisionBridgeVolunteerApp> {
  late final ApiClient api = widget.apiClient ?? ApiClient();
  late final SessionStore session = widget.sessionStore ?? SessionStore();
  bool loading = true;
  bool privacyAccepted = false;
  String? token;

  @override
  void initState() {
    super.initState();
    _restore();
  }

  Future<void> _restore() async {
    privacyAccepted = await session.hasPrivacyConsent();
    token = await session.readToken();
    api.token = token;
    if (token != null && token!.isNotEmpty) {
      try {
        await api.me();
      } on ApiException catch (exception) {
        if (exception.statusCode == 401) {
          token = null;
          api.token = null;
          await session.clearToken();
        }
      } catch (_) {
        // Keep a valid-looking local session during a temporary network outage.
      }
    }
    if (mounted) setState(() => loading = false);
  }

  Future<void> _acceptPrivacy() async {
    await session.savePrivacyConsent();
    setState(() => privacyAccepted = true);
  }

  Future<void> _authenticated(String nextToken) async {
    api.token = nextToken;
    await session.saveToken(nextToken);
    setState(() => token = nextToken);
  }

  Future<void> _logout() async {
    try {
      await api.logout();
    } catch (_) {
      // Local session must still be removable while offline.
    }
    api.token = null;
    await session.clearToken();
    if (mounted) setState(() => token = null);
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '视桥志愿者',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      home: loading
          ? const _LaunchScreen()
          : !privacyAccepted
              ? PrivacyScreen(onAccepted: _acceptPrivacy)
              : token == null
                  ? AuthScreen(api: api, onAuthenticated: _authenticated)
                  : HomeShell(api: api, onLogout: _logout),
    );
  }
}

class _LaunchScreen extends StatelessWidget {
  const _LaunchScreen();

  @override
  Widget build(BuildContext context) =>
      const Scaffold(body: Center(child: CircularProgressIndicator()));
}
