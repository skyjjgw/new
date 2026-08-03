import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../api_client.dart';
import '../app_theme.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen(
      {super.key, required this.api, required this.onAuthenticated});
  final ApiClient api;
  final Future<void> Function(String token) onAuthenticated;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final email = TextEditingController();
  final code = TextEditingController();
  final displayName = TextEditingController();
  bool codeSent = false;
  bool busy = false;
  String error = '';
  int countdown = 0;
  Timer? timer;

  @override
  void dispose() {
    timer?.cancel();
    email.dispose();
    code.dispose();
    displayName.dispose();
    super.dispose();
  }

  void _startCountdown() {
    countdown = 60;
    timer?.cancel();
    timer = Timer.periodic(const Duration(seconds: 1), (value) {
      if (!mounted) return value.cancel();
      if (countdown <= 1) {
        value.cancel();
        setState(() => countdown = 0);
      } else {
        setState(() => countdown--);
      }
    });
  }

  Future<void> _requestCode() async {
    if (!email.text.contains('@')) {
      setState(() => error = '请输入有效邮箱地址');
      return;
    }
    setState(() {
      busy = true;
      error = '';
    });
    try {
      final receipt = await widget.api.requestEmailCode(email.text.trim());
      if (!mounted) return;
      setState(() {
        codeSent = true;
        if (receipt.debugCode.isNotEmpty) {
          code.text = receipt.debugCode;
        }
      });
      _startCountdown();
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(
          content: Text(
              receipt.debugCode.isEmpty ? '验证码已发送，请检查邮箱' : '本地调试模式：验证码已自动填入')));
    } on ApiException catch (exception) {
      setState(() => error = exception.message);
    } catch (_) {
      setState(() => error = '暂时无法连接视桥服务器');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _verify() async {
    final name = displayName.text.trim();
    if (name.length > 30) {
      setState(() => error = '志愿者昵称不能超过 30 个字符');
      return;
    }
    if (code.text.trim().length != 6) {
      setState(() => error = '请输入 6 位验证码');
      return;
    }
    setState(() {
      busy = true;
      error = '';
    });
    try {
      final result = await widget.api
          .verifyEmailCode(email.text.trim(), code.text.trim(), name);
      await widget.onAuthenticated(result.token);
    } on ApiException catch (exception) {
      if (mounted) setState(() => error = exception.message);
    } catch (_) {
      if (mounted) setState(() => error = '登录失败，请检查网络后重试');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(
                        width: 58,
                        height: 58,
                        alignment: Alignment.center,
                        decoration: BoxDecoration(
                            color: AppTheme.teal,
                            borderRadius: BorderRadius.circular(18)),
                        child: const Icon(Icons.volunteer_activism_rounded,
                            color: Colors.white, size: 30)),
                    const SizedBox(height: 26),
                    const Text('欢迎加入视桥',
                        style: TextStyle(
                            fontSize: 30,
                            fontWeight: FontWeight.w800,
                            color: AppTheme.ink)),
                    const SizedBox(height: 8),
                    Text('使用邮箱验证码安全登录，无需设置或记忆密码。',
                        style: TextStyle(
                            color: Colors.blueGrey.shade600, height: 1.5)),
                    const SizedBox(height: 30),
                    TextField(
                        controller: email,
                        keyboardType: TextInputType.emailAddress,
                        textInputAction: TextInputAction.done,
                        autofillHints: const [AutofillHints.email],
                        autocorrect: false,
                        enableSuggestions: false,
                        enabled: !codeSent,
                        decoration: const InputDecoration(
                            labelText: '邮箱地址',
                            prefixIcon: Icon(Icons.mail_outline))),
                    if (codeSent) ...[
                      const SizedBox(height: 13),
                      TextField(
                          controller: displayName,
                          decoration: const InputDecoration(
                              labelText: '志愿者昵称（可留空）',
                              helperText: '1–30 个字符；留空将使用邮箱前缀',
                              prefixIcon: Icon(Icons.badge_outlined))),
                      const SizedBox(height: 13),
                      TextField(
                          controller: code,
                          keyboardType: TextInputType.number,
                          autofillHints: const [AutofillHints.oneTimeCode],
                          inputFormatters: [
                            FilteringTextInputFormatter.digitsOnly
                          ],
                          maxLength: 6,
                          decoration: InputDecoration(
                              labelText: '6 位验证码',
                              counterText: '',
                              prefixIcon:
                                  const Icon(Icons.verified_user_outlined),
                              suffixIcon: TextButton(
                                  onPressed: countdown == 0 && !busy
                                      ? _requestCode
                                      : null,
                                  child: Text(countdown > 0
                                      ? '${countdown}s'
                                      : '重发')))),
                    ],
                    if (error.isNotEmpty)
                      Padding(
                          padding: const EdgeInsets.only(top: 12),
                          child: Row(children: [
                            const Icon(Icons.error_outline,
                                color: Colors.redAccent, size: 18),
                            const SizedBox(width: 7),
                            Expanded(
                                child: Text(error,
                                    style: const TextStyle(
                                        color: Colors.redAccent, fontSize: 12)))
                          ])),
                    const SizedBox(height: 18),
                    FilledButton(
                        onPressed: busy
                            ? null
                            : codeSent
                                ? _verify
                                : _requestCode,
                        child: Text(busy
                            ? '请稍候…'
                            : codeSent
                                ? '验证并登录'
                                : '获取邮箱验证码')),
                    if (codeSent)
                      TextButton(
                          onPressed: busy
                              ? null
                              : () => setState(() {
                                    codeSent = false;
                                    code.clear();
                                    error = '';
                                  }),
                          child: const Text('更换邮箱')),
                    const SizedBox(height: 24),
                    const Row(children: [
                      Icon(Icons.shield_outlined,
                          size: 17, color: AppTheme.teal),
                      SizedBox(width: 7),
                      Expanded(
                          child: Text('验证码由视桥自有云发送，App 不接触 QQ 邮箱授权码。',
                              style: TextStyle(
                                  fontSize: 11, color: Colors.blueGrey)))
                    ])
                  ]),
            ),
          ),
        ),
      ),
    );
  }
}
