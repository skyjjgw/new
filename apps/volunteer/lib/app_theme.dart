import 'package:flutter/material.dart';

class AppTheme {
  static const ink = Color(0xFF173347);
  static const teal = Color(0xFF0B9B91);
  static const cyan = Color(0xFF4BC6C1);
  static const warm = Color(0xFFF4A261);
  static const canvas = Color(0xFFF3F7F8);

  static ThemeData get light {
    final scheme = ColorScheme.fromSeed(
        seedColor: teal, brightness: Brightness.light, surface: Colors.white);
    return ThemeData(
      useMaterial3: true,
      colorScheme:
          scheme.copyWith(primary: teal, secondary: warm, onSurface: ink),
      scaffoldBackgroundColor: canvas,
      fontFamilyFallback: const [
        'Microsoft YaHei',
        'PingFang SC',
        'Noto Sans CJK SC'
      ],
      appBarTheme: const AppBarTheme(
          backgroundColor: Colors.transparent,
          foregroundColor: ink,
          elevation: 0),
      cardTheme: CardTheme(
          elevation: 0,
          color: Colors.white,
          shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(20),
              side: const BorderSide(color: Color(0xFFE4EEF0)))),
      inputDecorationTheme: InputDecorationTheme(
          filled: true,
          fillColor: Colors.white,
          border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: const BorderSide(color: Color(0xFFD8E6E8))),
          enabledBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(14),
              borderSide: const BorderSide(color: Color(0xFFD8E6E8)))),
      filledButtonTheme: FilledButtonThemeData(
          style: FilledButton.styleFrom(
              minimumSize: const Size.fromHeight(50),
              shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14)))),
    );
  }
}
