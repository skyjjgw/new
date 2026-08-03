import 'dart:math' as math;

import 'models.dart';

const _pi = math.pi;
const _a = 6378245.0;
const _ee = 0.00669342162296594323;

MapSelection wgs84ToGcj02({
  required double lat,
  required double lng,
  String address = '',
  double? accuracy,
}) {
  if (!_insideMainlandChina(lat, lng)) {
    return MapSelection(
        lat: lat,
        lng: lng,
        address: address,
        source: 'gps',
        accuracy: accuracy);
  }
  var dLat = _transformLat(lng - 105, lat - 35);
  var dLng = _transformLng(lng - 105, lat - 35);
  final radLat = lat / 180 * _pi;
  var magic = math.sin(radLat);
  magic = 1 - _ee * magic * magic;
  final sqrtMagic = math.sqrt(magic);
  dLat = (dLat * 180) / ((_a * (1 - _ee)) / (magic * sqrtMagic) * _pi);
  dLng = (dLng * 180) / (_a / sqrtMagic * math.cos(radLat) * _pi);
  return MapSelection(
      lat: lat + dLat,
      lng: lng + dLng,
      address: address,
      source: 'gps',
      accuracy: accuracy);
}

double distanceMeters(MapSelection from, double lat, double lng) {
  const radius = 6371000.0;
  final dLat = (lat - from.lat) * _pi / 180;
  final dLng = (lng - from.lng) * _pi / 180;
  final a = math.sin(dLat / 2) * math.sin(dLat / 2) +
      math.cos(from.lat * _pi / 180) *
          math.cos(lat * _pi / 180) *
          math.sin(dLng / 2) *
          math.sin(dLng / 2);
  return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a));
}

bool _insideMainlandChina(double lat, double lng) =>
    lng >= 72.004 && lng <= 137.8347 && lat >= 0.8293 && lat <= 55.8271;

double _transformLat(double x, double y) {
  var value =
      -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * math.sqrt(x.abs());
  value += (20 * math.sin(6 * x * _pi) + 20 * math.sin(2 * x * _pi)) * 2 / 3;
  value += (20 * math.sin(y * _pi) + 40 * math.sin(y / 3 * _pi)) * 2 / 3;
  value +=
      (160 * math.sin(y / 12 * _pi) + 320 * math.sin(y * _pi / 30)) * 2 / 3;
  return value;
}

double _transformLng(double x, double y) {
  var value =
      300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * math.sqrt(x.abs());
  value += (20 * math.sin(6 * x * _pi) + 20 * math.sin(2 * x * _pi)) * 2 / 3;
  value += (20 * math.sin(x * _pi) + 40 * math.sin(x / 3 * _pi)) * 2 / 3;
  value +=
      (150 * math.sin(x / 12 * _pi) + 300 * math.sin(x / 30 * _pi)) * 2 / 3;
  return value;
}
