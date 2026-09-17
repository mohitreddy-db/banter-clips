/// Ported from `UserOut` / `PreferencesOut` in `backend/app/schemas.py`.
///
/// These are hand-written rather than generated with freezed. The shapes are
/// small and stable, and a `fromJson` you can read is worth more here than
/// one you have to run `build_runner` to regenerate every time the API moves.
library;

class Preferences {
  const Preferences({
    this.sports = const [],
    this.teams = const [],
    this.players = const [],
    this.role,
    this.onboardingCompleted = false,
  });

  final List<String> sports;
  final List<String> teams;
  final List<String> players;
  final String? role;
  final bool onboardingCompleted;

  bool get isEmpty => sports.isEmpty && teams.isEmpty && players.isEmpty;

  /// Everything the user picked, in one list — the Account screen shows them
  /// as a single row of chips.
  List<String> get allTags => [...sports, ...teams, ...players];

  factory Preferences.fromJson(Map<String, dynamic> json) => Preferences(
    sports: _strings(json['sports']),
    teams: _strings(json['teams']),
    players: _strings(json['players']),
    role: json['role'] as String?,
    onboardingCompleted: json['onboarding_completed'] as bool? ?? false,
  );

  Preferences copyWith({
    List<String>? sports,
    List<String>? teams,
    List<String>? players,
    String? role,
    bool? onboardingCompleted,
  }) => Preferences(
    sports: sports ?? this.sports,
    teams: teams ?? this.teams,
    players: players ?? this.players,
    role: role ?? this.role,
    onboardingCompleted: onboardingCompleted ?? this.onboardingCompleted,
  );
}

class User {
  const User({
    required this.id,
    required this.email,
    required this.plan,
    this.displayName,
    this.cancelAtPeriodEnd = false,
    this.createdAt,
    this.preferences = const Preferences(),
    this.isAdmin = false,
  });

  final String id;
  final String email;
  final String? displayName;

  /// "free" | "creator". Gating is derived from [Usage] where possible —
  /// this is the fallback the web app also falls back to.
  final String plan;
  final bool cancelAtPeriodEnd;
  final DateTime? createdAt;
  final Preferences preferences;
  final bool isAdmin;

  bool get isCreator => plan == 'creator';

  /// First letter for the avatar tile, matching the web's fallback chain.
  String get initial {
    final source = (displayName?.isNotEmpty ?? false) ? displayName! : email;
    return source.isEmpty ? '?' : source[0].toUpperCase();
  }

  factory User.fromJson(Map<String, dynamic> json) => User(
    id: json['id'].toString(),
    email: json['email'] as String? ?? '',
    displayName: json['display_name'] as String?,
    plan: json['plan'] as String? ?? 'free',
    cancelAtPeriodEnd: json['cancel_at_period_end'] as bool? ?? false,
    createdAt: DateTime.tryParse(json['created_at']?.toString() ?? ''),
    preferences: json['preferences'] is Map
        ? Preferences.fromJson(
            Map<String, dynamic>.from(json['preferences'] as Map),
          )
        : const Preferences(),
    isAdmin: json['is_admin'] as bool? ?? false,
  );

  User copyWith({
    String? plan,
    bool? cancelAtPeriodEnd,
    Preferences? preferences,
  }) => User(
    id: id,
    email: email,
    displayName: displayName,
    plan: plan ?? this.plan,
    cancelAtPeriodEnd: cancelAtPeriodEnd ?? this.cancelAtPeriodEnd,
    createdAt: createdAt,
    preferences: preferences ?? this.preferences,
    isAdmin: isAdmin,
  );
}

/// `UsageOut` — the authority on what this account may do this month.
/// Every gate in the UI reads from here, never from a local count.
class Usage {
  const Usage({
    required this.plan,
    required this.used,
    required this.limit,
    required this.left,
    required this.canDownload,
    required this.watermarked,
    this.credits = 0,
    this.prices = const CreditPrices(),
  });

  final String plan;
  final int used;

  /// Null on the credits model — there is no monthly video cap any more, the
  /// wallet is the limit. Kept for older "X of Y" responses.
  final int? limit;
  final int left;

  /// BR-08: Free is publish-only. Download is a Creator feature.
  final bool canDownload;

  /// Frozen per-clip at creation time server-side; this is the current
  /// account-level answer, used to word the UI before a clip exists.
  final bool watermarked;
  final int credits;
  final CreditPrices prices;

  bool get isCreator => plan == 'creator';
  double get fraction {
    final cap = limit;
    if (cap == null || cap <= 0) return 0;
    return (used / cap).clamp(0, 1).toDouble();
  }

  factory Usage.fromJson(Map<String, dynamic> json) => Usage(
    plan: json['plan'] as String? ?? 'free',
    used: (json['used'] as num?)?.toInt() ?? 0,
    limit: (json['limit'] as num?)?.toInt(),
    left: (json['left'] as num?)?.toInt() ?? 0,
    canDownload: json['can_download'] as bool? ?? false,
    watermarked: json['watermarked'] as bool? ?? true,
    credits:
        (json['credits'] as num?)?.toInt() ??
        (json['left'] as num?)?.toInt() ??
        0,
    prices: json['prices'] is Map
        ? CreditPrices.fromJson(
            Map<String, dynamic>.from(json['prices'] as Map),
          )
        : const CreditPrices(),
  );

  /// What the app assumes before `/me/usage` has answered. Deliberately the
  /// pessimistic Free shape: never show a locked feature as unlocked.
  static const unknown = Usage(
    plan: 'free',
    used: 0,
    limit: 60,
    left: 60,
    canDownload: false,
    watermarked: true,
    credits: 60,
  );
}

class CreditPrices {
  const CreditPrices({
    this.perSecond720 = 4,
    this.perSecond1080 = 7,
    this.enhanceTake = 1,
  });
  final int perSecond720;
  final int perSecond1080;
  final int enhanceTake;

  int video(int seconds, String resolution) =>
      seconds * (resolution == '1080p' ? perSecond1080 : perSecond720);

  factory CreditPrices.fromJson(Map<String, dynamic> json) {
    final perSecond = json['per_second'] is Map
        ? Map<String, dynamic>.from(json['per_second'] as Map)
        : const <String, dynamic>{};
    return CreditPrices(
      perSecond720: (perSecond['720p'] as num?)?.toInt() ?? 4,
      perSecond1080: (perSecond['1080p'] as num?)?.toInt() ?? 7,
      enhanceTake: (json['enhance_take'] as num?)?.toInt() ?? 1,
    );
  }
}

List<String> _strings(dynamic value) =>
    value is List ? value.map((e) => e.toString()).toList() : const [];
