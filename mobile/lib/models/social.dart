/// `SocialAccountOut` — a connected publishing destination.
///
/// One account per platform is the rule server-side, so the app treats the
/// list as "the Instagram account, or nothing" and never offers a picker.
class SocialAccount {
  const SocialAccount({
    required this.id,
    required this.platform,
    required this.handle,
    required this.status,
    this.connectedAt,
  });

  final String id;
  final String platform;
  final String handle;

  /// "connected" | "revoked". A revoked account is shown as disconnected so
  /// the user reconnects cleanly instead of watching publishes fail.
  final String status;
  final DateTime? connectedAt;

  bool get isConnected => status == 'connected';

  factory SocialAccount.fromJson(Map<String, dynamic> json) => SocialAccount(
    id: json['id'].toString(),
    platform: json['platform']?.toString() ?? '',
    handle: json['handle']?.toString() ?? '',
    status: json['status']?.toString() ?? 'connected',
    connectedAt: DateTime.tryParse(json['connected_at']?.toString() ?? ''),
  );
}

/// `TakeVariation` — one sharper wording of the user's take, offered on the
/// create screen. Never imposed: the user's own words stay selected unless
/// they pick one of these.
class TakeVariation {
  const TakeVariation({required this.take, this.angle = '', this.why = ''});

  final String take;

  /// A 2–4 word label for the angle taken ("Crowns the winner").
  final String angle;

  /// Why this angle lands, shown as a hint under the option.
  final String why;

  factory TakeVariation.fromJson(Map<String, dynamic> json) => TakeVariation(
    take: json['take']?.toString() ?? '',
    angle: json['angle']?.toString() ?? '',
    why: json['why']?.toString() ?? '',
  );
}

/// One ready-to-shoot take attached to a trending topic.
class TrendingPrompt {
  const TrendingPrompt({
    required this.take,
    this.tone = 'Funny',
    this.seconds = 15,
    this.angle = '',
  });

  final String take;
  final String tone;
  final int seconds;
  final String angle;

  factory TrendingPrompt.fromJson(Map<String, dynamic> json) => TrendingPrompt(
    take: json['take']?.toString() ?? '',
    tone: json['tone']?.toString() ?? 'Funny',
    seconds: (json['seconds'] as num?)?.toInt() ?? 15,
    angle: json['angle']?.toString() ?? '',
  );
}

/// A story fans are talking about right now, with takes written for it.
/// The feed comes from a shared 20-minute server cache, so opening the
/// create screen repeatedly costs nothing.
class TrendingTopic {
  const TrendingTopic({
    required this.title,
    this.summary = '',
    this.whyNow = '',
    this.heat = 'hot',
    this.who = const [],
    this.team = '',
    this.prompts = const [],
  });

  final String title;
  final String summary;
  final String whyNow;

  /// "viral" | "hot" | "rising" — drives the badge colour.
  final String heat;
  final List<String> who;
  final String team;
  final List<TrendingPrompt> prompts;

  factory TrendingTopic.fromJson(Map<String, dynamic> json) => TrendingTopic(
    title: json['title']?.toString() ?? '',
    summary: json['summary']?.toString() ?? '',
    whyNow: json['why_now']?.toString() ?? '',
    heat: json['heat']?.toString() ?? 'hot',
    who: json['who'] is List
        ? (json['who'] as List).map((e) => e.toString()).toList()
        : const [],
    team: json['team']?.toString() ?? '',
    prompts: json['prompts'] is List
        ? (json['prompts'] as List)
              .whereType<Map>()
              .map((e) => TrendingPrompt.fromJson(Map<String, dynamic>.from(e)))
              .toList()
        : const [],
  );
}

/// The whole feed. An empty topic list is a valid answer — it means web
/// research is off server-side, and the section simply hides itself.
class TrendingFeed {
  const TrendingFeed({this.topics = const [], this.fetchedAt});

  final List<TrendingTopic> topics;
  final DateTime? fetchedAt;

  bool get isEmpty => topics.isEmpty;

  factory TrendingFeed.fromJson(Map<String, dynamic> json) => TrendingFeed(
    topics: json['topics'] is List
        ? (json['topics'] as List)
              .whereType<Map>()
              .map((e) => TrendingTopic.fromJson(Map<String, dynamic>.from(e)))
              .toList()
        : const [],
    fetchedAt: DateTime.tryParse(json['fetched_at']?.toString() ?? ''),
  );
}
