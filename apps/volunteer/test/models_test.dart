import 'package:flutter_test/flutter_test.dart';
import 'package:visionbridge_volunteer/models.dart';

void main() {
  test('map obstacle carries public task state for direct claiming', () {
    final obstacle = Obstacle.fromJson({
      'id': 'OBS-1',
      'categoryLabel': '临时杂物/堆放',
      'description': '盲道被纸箱占用',
      'address': '学院路',
      'lat': 28.6,
      'lng': 121.1,
      'photoUrl': '/photo',
      'priority': 'normal',
      'status': 'open',
      'taskId': 'VBT-1',
      'taskStatus': 'open',
    });

    expect(obstacle.taskId, 'VBT-1');
    expect(obstacle.isClaimable, isTrue);
    expect(obstacle.toMapJson()['taskStatus'], 'open');
  });
}
