class PublicConfig {
  const PublicConfig(
      {this.amapKey = '',
      this.amapSecurityCode = '',
      this.defaultCenter = const [121.138923, 28.632112]});

  final String amapKey;
  final String amapSecurityCode;
  final List<double> defaultCenter;

  factory PublicConfig.fromJson(Map<String, dynamic> json) => PublicConfig(
        amapKey: json['amapKey'] as String? ?? '',
        amapSecurityCode: json['amapSecurityCode'] as String? ?? '',
        defaultCenter: (json['defaultCenter'] as List<dynamic>? ??
                const [121.138923, 28.632112])
            .map((value) => (value as num).toDouble())
            .toList(),
      );

  Map<String, dynamic> toJson() => {
        'amapKey': amapKey,
        'amapSecurityCode': amapSecurityCode,
        'defaultCenter': defaultCenter,
      };
}

class MapSelection {
  const MapSelection({
    required this.lat,
    required this.lng,
    this.address = '',
    this.source = 'map',
    this.accuracy,
  });

  final double lat;
  final double lng;
  final String address;
  final String source;
  final double? accuracy;

  MapSelection copyWith({
    double? lat,
    double? lng,
    String? address,
    String? source,
    double? accuracy,
  }) =>
      MapSelection(
        lat: lat ?? this.lat,
        lng: lng ?? this.lng,
        address: address ?? this.address,
        source: source ?? this.source,
        accuracy: accuracy ?? this.accuracy,
      );

  Map<String, dynamic> toJson() => {
        'lat': lat,
        'lng': lng,
        'address': address,
        'source': source,
      };

  factory MapSelection.fromJson(Map<String, dynamic> json) => MapSelection(
        lat: (json['lat'] as num).toDouble(),
        lng: (json['lng'] as num).toDouble(),
        address: json['address'] as String? ?? '',
        source: json['source'] as String? ?? 'map',
      );
}

class UserProfile {
  const UserProfile(
      {required this.id,
      required this.email,
      required this.displayName,
      required this.role});
  final String id;
  final String email;
  final String displayName;
  final String role;

  factory UserProfile.fromJson(Map<String, dynamic> json) => UserProfile(
        id: json['id'] as String,
        email: json['email'] as String,
        displayName: json['displayName'] as String,
        role: json['role'] as String? ?? 'volunteer',
      );
}

class Obstacle {
  const Obstacle(
      {required this.id,
      required this.categoryLabel,
      required this.description,
      required this.address,
      required this.lat,
      required this.lng,
      required this.photoUrl,
      required this.priority,
      required this.status,
      this.taskId,
      this.taskStatus});
  final String id;
  final String categoryLabel;
  final String description;
  final String address;
  final double lat;
  final double lng;
  final String photoUrl;
  final String priority;
  final String status;
  final String? taskId;
  final String? taskStatus;

  bool get isClaimable => taskId != null && taskStatus == 'open';

  factory Obstacle.fromJson(Map<String, dynamic> json) => Obstacle(
        id: json['id'] as String,
        categoryLabel: json['categoryLabel'] as String,
        description: json['description'] as String,
        address: json['address'] as String,
        lat: (json['lat'] as num).toDouble(),
        lng: (json['lng'] as num).toDouble(),
        photoUrl: json['photoUrl'] as String? ?? '',
        priority: json['priority'] as String? ?? 'normal',
        status: json['status'] as String? ?? 'open',
        taskId: json['taskId'] as String?,
        taskStatus: json['taskStatus'] as String?,
      );

  Map<String, dynamic> toMapJson() => {
        'id': id,
        'lat': lat,
        'lng': lng,
        'priority': priority,
        'taskStatus': taskStatus,
      };
}

class TaskItem {
  const TaskItem(
      {required this.id,
      required this.obstacleId,
      required this.title,
      required this.description,
      required this.categoryLabel,
      required this.address,
      required this.lat,
      required this.lng,
      required this.photoUrl,
      required this.priority,
      required this.status,
      this.assigneeId,
      this.completionNote = '',
      this.reviewNote = ''});
  final String id;
  final String obstacleId;
  final String title;
  final String description;
  final String categoryLabel;
  final String address;
  final double lat;
  final double lng;
  final String photoUrl;
  final String priority;
  final String status;
  final String? assigneeId;
  final String completionNote;
  final String reviewNote;

  factory TaskItem.fromJson(Map<String, dynamic> json) => TaskItem(
        id: json['id'] as String,
        obstacleId: json['obstacleId'] as String,
        title: json['title'] as String,
        description: json['description'] as String,
        categoryLabel: json['categoryLabel'] as String,
        address: json['address'] as String,
        lat: (json['lat'] as num).toDouble(),
        lng: (json['lng'] as num).toDouble(),
        photoUrl: json['photoUrl'] as String? ?? '',
        priority: json['priority'] as String? ?? 'normal',
        status: json['status'] as String? ?? 'open',
        assigneeId: json['assigneeId'] as String?,
        completionNote: json['completionNote'] as String? ?? '',
        reviewNote: json['reviewNote'] as String? ?? '',
      );
}

class ReportItem {
  const ReportItem(
      {required this.id,
      required this.categoryLabel,
      required this.description,
      required this.status,
      required this.reviewNote,
      required this.createdAt,
      this.cleanupReasonLabel = '',
      this.address = '',
      this.lat = 0,
      this.lng = 0,
      this.photoUrl = '',
      this.priority = 'normal',
      this.canDelete = false});
  final String id;
  final String categoryLabel;
  final String description;
  final String status;
  final String reviewNote;
  final DateTime createdAt;
  final String cleanupReasonLabel;
  final String address;
  final double lat;
  final double lng;
  final String photoUrl;
  final String priority;
  final bool canDelete;

  factory ReportItem.fromJson(Map<String, dynamic> json) => ReportItem(
        id: json['id'] as String,
        categoryLabel: json['categoryLabel'] as String,
        description: json['description'] as String,
        status: json['status'] as String,
        reviewNote: json['reviewNote'] as String? ?? '',
        createdAt: DateTime.parse(json['createdAt'] as String),
        cleanupReasonLabel: json['cleanupReasonLabel'] as String? ?? '',
        address: json['address'] as String? ?? '',
        lat: (json['lat'] as num?)?.toDouble() ?? 0,
        lng: (json['lng'] as num?)?.toDouble() ?? 0,
        photoUrl: json['photoUrl'] as String? ?? '',
        priority: json['priority'] as String? ?? 'normal',
        canDelete: json['canDelete'] as bool? ?? false,
      );
}
