import 'package:shared_preferences/shared_preferences.dart';

class SessionStore {
  static const _tokenKey = 'visionbridge_user_token';
  static const _privacyKey = 'visionbridge_privacy_consent_v1';

  Future<String?> readToken() async =>
      (await SharedPreferences.getInstance()).getString(_tokenKey);

  Future<void> saveToken(String token) async =>
      (await SharedPreferences.getInstance()).setString(_tokenKey, token);

  Future<void> clearToken() async =>
      (await SharedPreferences.getInstance()).remove(_tokenKey);

  Future<bool> hasPrivacyConsent() async =>
      (await SharedPreferences.getInstance()).getBool(_privacyKey) ?? false;

  Future<void> savePrivacyConsent() async =>
      (await SharedPreferences.getInstance()).setBool(_privacyKey, true);
}
