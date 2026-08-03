import 'package:flutter_test/flutter_test.dart';
import 'package:visionbridge_volunteer/geo_utils.dart';
import 'package:visionbridge_volunteer/models.dart';

void main() {
  test('converts mainland WGS84 coordinates for AMap display', () {
    final converted = wgs84ToGcj02(lat: 39.9087, lng: 116.3975);
    expect((converted.lat - 39.9087).abs(), greaterThan(.001));
    expect((converted.lng - 116.3975).abs(), greaterThan(.001));
    expect((converted.lat - 39.9087).abs(), lessThan(.02));
    expect((converted.lng - 116.3975).abs(), lessThan(.02));
    expect(converted.source, 'gps');
  });

  test('keeps coordinates outside mainland China unchanged', () {
    final converted = wgs84ToGcj02(lat: 51.5074, lng: -.1278);
    expect(converted.lat, 51.5074);
    expect(converted.lng, -.1278);
  });

  test('calculates useful task distance', () {
    const origin = MapSelection(lat: 28.632112, lng: 121.138923);
    expect(distanceMeters(origin, origin.lat, origin.lng), closeTo(0, .01));
    expect(distanceMeters(origin, 28.633112, 121.138923),
        inInclusiveRange(105, 118));
  });
}
