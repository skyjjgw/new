import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';

import 'models.dart';

class ApiException implements Exception {
  const ApiException(this.message, {this.statusCode});
  final String message;
  final int? statusCode;
  @override
  String toString() => message;
}

class AuthResult {
  const AuthResult({required this.token, required this.user});
  final String token;
  final UserProfile user;
}

class EmailCodeReceipt {
  const EmailCodeReceipt({required this.expiresIn, this.debugCode = ''});
  final int expiresIn;
  final String debugCode;
}

class ApiClient {
  ApiClient({String? baseUrl, http.Client? client})
      : baseUrl = _normalizeBase(baseUrl ??
            const String.fromEnvironment('VISIONBRIDGE_API_BASE',
                defaultValue: 'same-origin')),
        _client = client ?? http.Client();

  final String baseUrl;
  final http.Client _client;
  String? token;
  static const requestTimeout = Duration(seconds: 20);
  static const uploadTimeout = Duration(seconds: 45);

  static String _normalizeBase(String value) =>
      value == 'same-origin' ? '' : value.replaceAll(RegExp(r'/$'), '');

  Uri _uri(String path) => Uri.parse('$baseUrl$path');
  String resolveUrl(String path) =>
      path.startsWith('http') ? path : '$baseUrl$path';

  Map<String, String> get _headers => {
        'Accept': 'application/json',
        if (token != null && token!.isNotEmpty)
          'Authorization': 'Bearer $token',
      };

  dynamic _decode(http.Response response) {
    dynamic body;
    try {
      body = jsonDecode(utf8.decode(response.bodyBytes));
    } catch (_) {
      body = null;
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      final detail = body is Map<String, dynamic> ? body['detail'] : null;
      throw ApiException(_friendlyError(detail, response.statusCode),
          statusCode: response.statusCode);
    }
    return body;
  }

  String _friendlyError(dynamic detail, int statusCode) {
    if (detail is List && detail.isNotEmpty) {
      final first = detail.first;
      if (first is Map) {
        final location = (first['loc'] as List?)?.join('.') ?? '';
        if (location.contains('displayName') ||
            location.contains('display_name')) {
          return '志愿者昵称请填写 1–30 个字符，也可以留空使用默认昵称';
        }
        if (location.contains('code')) return '请输入邮件中的 6 位验证码';
        if (location.contains('email')) return '请输入有效的邮箱地址';
      }
      return '提交内容格式不正确，请检查后重试';
    }
    final value = detail?.toString() ?? '';
    const messages = {
      'please wait before requesting another code': '验证码刚刚已发送，请稍后再试',
      'too many verification emails': '验证码请求过于频繁，请一小时后再试',
      'verification code must contain 6 digits': '请输入邮件中的 6 位验证码',
      'verification code is unavailable': '验证码已失效，请重新获取',
      'verification code has expired': '验证码已过期，请重新获取',
      'verification attempts exceeded': '验证码错误次数过多，请重新获取',
      'verification code is incorrect': '验证码不正确，请核对邮件后重试',
      'missing user token': '登录状态已失效，请重新登录',
      'invalid or expired user token': '登录状态已失效，请重新登录',
      'email service is not configured': '邮件服务暂未配置，请联系管理员',
      'verification email could not be sent': '验证码邮件发送失败，请稍后重试',
      'only JPEG, PNG and WebP images are supported': '仅支持 JPEG、PNG 或 WebP 图片',
      'image must be between 1 byte and 8 MiB': '图片不能超过 8 MB',
      'report not found': '没有找到这条上报，可能已被删除',
      'approved reports are public records and cannot be deleted by the reporter':
          '该上报已审核进入公共地图，不能由个人直接删除；如需撤销请联系管理员',
    };
    if (messages.containsKey(value)) return messages[value]!;
    if (statusCode == 401) return '登录状态已失效，请重新登录';
    if (statusCode == 413) return '图片过大，请重新拍摄或压缩后上传';
    if (statusCode == 429) return '操作过于频繁，请稍后再试';
    return value.isEmpty ? '服务器请求失败（$statusCode）' : value;
  }

  Future<http.Response> _await(Future<http.Response> future) async {
    try {
      return await future.timeout(requestTimeout);
    } on TimeoutException {
      throw const ApiException('连接服务器超时，请检查网络后重试');
    }
  }

  Future<http.Response> _awaitUpload(http.BaseRequest request) async {
    try {
      final streamed = await _client.send(request).timeout(uploadTimeout);
      return await http.Response.fromStream(streamed).timeout(uploadTimeout);
    } on TimeoutException {
      throw const ApiException('图片上传超时，内容已保留，请稍后重试');
    }
  }

  Future<EmailCodeReceipt> requestEmailCode(String email) async {
    final response = await _await(_client.post(
      _uri('/api/v1/auth/email/request'),
      headers: {..._headers, 'Content-Type': 'application/json'},
      body: jsonEncode({'email': email.trim().toLowerCase()}),
    ));
    final body = _decode(response) as Map<String, dynamic>;
    return EmailCodeReceipt(
      expiresIn: body['expiresIn'] as int? ?? 600,
      debugCode: body['debugCode'] as String? ?? '',
    );
  }

  Future<AuthResult> verifyEmailCode(
      String email, String code, String displayName) async {
    final name = displayName.trim();
    final payload = <String, dynamic>{
      'email': email.trim().toLowerCase(),
      'code': code
    };
    if (name.isNotEmpty) payload['displayName'] = name;
    final response = await _await(_client.post(
      _uri('/api/v1/auth/email/verify'),
      headers: {..._headers, 'Content-Type': 'application/json'},
      body: jsonEncode(payload),
    ));
    final body = _decode(response) as Map<String, dynamic>;
    return AuthResult(
        token: body['token'] as String,
        user: UserProfile.fromJson(body['user'] as Map<String, dynamic>));
  }

  Future<UserProfile> me() async {
    final response =
        await _await(_client.get(_uri('/api/v1/auth/me'), headers: _headers));
    final body = _decode(response) as Map<String, dynamic>;
    return UserProfile.fromJson(body['user'] as Map<String, dynamic>);
  }

  Future<void> logout() async {
    final response = await _await(
        _client.post(_uri('/api/v1/auth/logout'), headers: _headers));
    _decode(response);
  }

  Future<PublicConfig> publicConfig() async {
    final response = await _await(
        _client.get(_uri('/api/v1/config/public'), headers: _headers));
    return PublicConfig.fromJson(_decode(response) as Map<String, dynamic>);
  }

  Future<List<Obstacle>> obstacles({bool includeResolved = false}) async {
    final response = await _await(_client.get(
        _uri('/api/v1/map/obstacles?includeResolved=$includeResolved'),
        headers: _headers));
    final body = _decode(response) as Map<String, dynamic>;
    return (body['items'] as List<dynamic>)
        .map((item) => Obstacle.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<TaskItem>> tasks({String status = 'open'}) async {
    final response = await _await(_client.get(
        _uri('/api/v1/volunteer/tasks?status=$status'),
        headers: _headers));
    final body = _decode(response) as Map<String, dynamic>;
    return (body['items'] as List<dynamic>)
        .map((item) => TaskItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<TaskItem>> myTasks() async {
    final response = await _await(
        _client.get(_uri('/api/v1/volunteer/tasks/mine'), headers: _headers));
    final body = _decode(response) as Map<String, dynamic>;
    return (body['items'] as List<dynamic>)
        .map((item) => TaskItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<List<ReportItem>> myReports() async {
    final response = await _await(
        _client.get(_uri('/api/v1/volunteer/reports/mine'), headers: _headers));
    final body = _decode(response) as Map<String, dynamic>;
    return (body['items'] as List<dynamic>)
        .map((item) => ReportItem.fromJson(item as Map<String, dynamic>))
        .toList();
  }

  Future<void> deleteReport(String reportId) async {
    final response = await _await(_client.delete(
      _uri('/api/v1/volunteer/reports/${Uri.encodeComponent(reportId)}'),
      headers: _headers,
    ));
    _decode(response);
  }

  Future<ReportItem> createReport({
    required String category,
    required String cleanupReason,
    required String description,
    required String address,
    required double lat,
    required double lng,
    required Uint8List photoBytes,
    required String photoName,
  }) async {
    final request =
        http.MultipartRequest('POST', _uri('/api/v1/volunteer/reports'))
          ..headers.addAll(_headers)
          ..fields.addAll({
            'category': category,
            'cleanupReason': cleanupReason,
            'description': description,
            'address': address,
            'lat': '$lat',
            'lng': '$lng'
          })
          ..files.add(http.MultipartFile.fromBytes('photo', photoBytes,
              filename: photoName, contentType: _imageType(photoName)));
    final response = await _awaitUpload(request);
    final body = _decode(response) as Map<String, dynamic>;
    return ReportItem.fromJson(body['report'] as Map<String, dynamic>);
  }

  Future<TaskItem> claimTask(String taskId) async {
    final response = await _await(_client.post(
        _uri('/api/v1/volunteer/tasks/$taskId/claim'),
        headers: _headers));
    final body = _decode(response) as Map<String, dynamic>;
    return TaskItem.fromJson(body['task'] as Map<String, dynamic>);
  }

  Future<TaskItem> completeTask(String taskId, String note,
      Uint8List photoBytes, String photoName) async {
    final request = http.MultipartRequest(
        'POST', _uri('/api/v1/volunteer/tasks/$taskId/complete'))
      ..headers.addAll(_headers)
      ..fields['note'] = note
      ..files.add(http.MultipartFile.fromBytes('photo', photoBytes,
          filename: photoName, contentType: _imageType(photoName)));
    final response = await _awaitUpload(request);
    final body = _decode(response) as Map<String, dynamic>;
    return TaskItem.fromJson(body['task'] as Map<String, dynamic>);
  }

  MediaType _imageType(String name) {
    final lower = name.toLowerCase();
    if (lower.endsWith('.png')) return MediaType('image', 'png');
    if (lower.endsWith('.webp')) return MediaType('image', 'webp');
    return MediaType('image', 'jpeg');
  }
}
