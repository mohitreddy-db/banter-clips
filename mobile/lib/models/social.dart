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
///
/// Also the shape of a one-tap *preset* on the Viral screen: a preset carries
/// a [key], an [icon] and a [label] as well, and its [take] is written for
/// the user rather than shown to them first.
class TrendingPrompt {
  const TrendingPrompt({
    required this.take,
    this.tone = 'Funny',
    this.seconds = 15,
    this.angle = '',
    this.key = '',
    this.icon = '',
    this.label = '',
  });

  final String take;
  final String tone;
  final int seconds;
  final String angle;
  final String key;
  final String icon;
  final String label;

  factory TrendingPrompt.fromJson(Map<String, dynamic> json) => TrendingPrompt(
    take: json['take']?.toString() ?? '',
    tone: json['tone']?.toString() ?? 'Funny',
    seconds: (json['seconds'] as num?)?.toInt() ?? 15,
    angle: json['angle']?.toString() ?? '',
    key: json['key']?.toString() ?? '',
    icon: json['icon']?.toString() ?? '',
    label: json['label']?.toString() ?? '',
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
    this.presets = const [],
  });

  final String title;
  final String summary;
  final String whyNow;

  /// "viral" | "hot" | "rising" — drives the badge colour.
  final String heat;
  final List<String> who;
  final String team;
  final List<TrendingPrompt> prompts;

  /// One-tap angles ("Hot take", "Roast it"…) the Viral screen shows above
  /// the ready-written takes.
  final List<TrendingPrompt> presets;

  factory TrendingTopic.fromJson(Map<String, dynamic> json) => TrendingTopic(
    title: json['title']?.toString() ?? '',
    summary: json['summary']?.toString() ?? '',
    whyNow: json['why_now']?.toString() ?? '',
    heat: json['heat']?.toString() ?? 'hot',
    who: json['who'] is List
        ? (json['who'] as List).map((e) => e.toString()).toList()
        : const [],
    team: json['team']?.toString() ?? '',
    prompts: _prompts(json['prompts']),
    presets: _prompts(json['presets']),
  );

  static List<TrendingPrompt> _prompts(dynamic value) => value is List
      ? value
            .whereType<Map>()
            .map((e) => TrendingPrompt.fromJson(Map<String, dynamic>.from(e)))
            .toList()
      : const [];
}

/// The whole feed. An empty topic list is a valid answer — it means web
/// research is off server-side, and the section simply hides itself.
class TrendingFeed {
  const TrendingFeed({
    this.topics = const [],
    this.fetchedAt,
    this.refreshAfter = 0,
  });

  final List<TrendingTopic> topics;
  final DateTime? fetchedAt;

  /// Seconds after [fetchedAt] before the server will rebuild the feed. A
  /// refresh pressed before then just returns the cache, so the button
  /// counts down instead.
  final int refreshAfter;

  bool get isEmpty => topics.isEmpty;

  /// Seconds until a refresh would actually do something; 0 = now.
  int get secondsUntilRefresh {
    final at = fetchedAt;
    if (at == null || refreshAfter <= 0) return 0;
    final elapsed = DateTime.now().difference(at).inSeconds;
    return (refreshAfter - elapsed).clamp(0, refreshAfter);
  }

  factory TrendingFeed.fromJson(Map<String, dynamic> json) => TrendingFeed(
    topics: json['topics'] is List
        ? (json['topics'] as List)
              .whereType<Map>()
              .map((e) => TrendingTopic.fromJson(Map<String, dynamic>.from(e)))
              .toList()
        : const [],
    fetchedAt: DateTime.tryParse(json['fetched_at']?.toString() ?? ''),
    refreshAfter: (json['refresh_after'] as num?)?.toInt() ?? 0,
  );
}

/// `TikTokCreatorInfo` — what TikTok says this account may post, fetched
/// right before publishing. TikTok's rules: the privacy list, the disabled
/// interactions and the unaudited flag all come from here, never from us.
class TikTokCreatorInfo {
  const TikTokCreatorInfo({
    required this.nickname,
    required this.username,
    required this.avatarUrl,
    required this.privacyLevelOptions,
    required this.commentDisabled,
    required this.duetDisabled,
    required this.stitchDisabled,
    required this.maxVideoPostDurationSec,
    required this.unaudited,
  });

  final String nickname;
  final String username;
  final String avatarUrl;
  final List<String> privacyLevelOptions;
  final bool commentDisabled;
  final bool duetDisabled;
  final bool stitchDisabled;
  final int maxVideoPostDurationSec;

  /// The app has not cleared TikTok's review yet: posts must be "Only me".
  final bool unaudited;

  factory TikTokCreatorInfo.fromJson(Map<String, dynamic> json) =>
      TikTokCreatorInfo(
        nickname: json['nickname']?.toString() ?? '',
        username: json['username']?.toString() ?? '',
        avatarUrl: json['avatar_url']?.toString() ?? '',
        privacyLevelOptions: json['privacy_level_options'] is List
            ? (json['privacy_level_options'] as List)
                  .map((e) => e.toString())
                  .toList()
            : const [],
        commentDisabled: json['comment_disabled'] as bool? ?? false,
        duetDisabled: json['duet_disabled'] as bool? ?? false,
        stitchDisabled: json['stitch_disabled'] as bool? ?? false,
        maxVideoPostDurationSec:
            (json['max_video_post_duration_sec'] as num?)?.toInt() ?? 0,
        unaudited: json['unaudited'] as bool? ?? false,
      );
}
