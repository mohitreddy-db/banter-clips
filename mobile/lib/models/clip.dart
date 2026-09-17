import 'script.dart';

/// `PublishOut` — one attempt at pushing a clip to a social account.
class Publish {
  const Publish({
    required this.id,
    required this.clipId,
    required this.socialAccountId,
    required this.caption,
    required this.status,
    this.error,
    this.externalUrl,
    this.platform,
    this.handle,
    this.createdAt,
    this.publishedAt,
  });

  final String id;
  final String clipId;
  final String socialAccountId;
  final String caption;

  /// "queued" | "uploading" | "published" | "failed".
  final String status;
  final String? error;

  /// The live post, once Instagram gives us a permalink.
  final String? externalUrl;
  final String? platform;
  final String? handle;
  final DateTime? createdAt;
  final DateTime? publishedAt;

  bool get inFlight => status == 'queued' || status == 'uploading';
  bool get isPublished => status == 'published';
  bool get hasFailed => status == 'failed';

  factory Publish.fromJson(Map<String, dynamic> json) => Publish(
    id: json['id'].toString(),
    clipId: json['clip_id'].toString(),
    socialAccountId: json['social_account_id'].toString(),
    caption: json['caption']?.toString() ?? '',
    status: json['status']?.toString() ?? 'queued',
    error: json['error'] as String?,
    externalUrl: json['external_url'] as String?,
    platform: json['platform'] as String?,
    handle: json['handle'] as String?,
    createdAt: DateTime.tryParse(json['created_at']?.toString() ?? ''),
    publishedAt: DateTime.tryParse(json['published_at']?.toString() ?? ''),
  );
}

/// The seven pipeline stages, in order, with the labels the web app shows.
/// `queued` is the pre-stage — it is not one of the seven, so the progress
/// list starts after it (`STAGES` in `Studio.jsx` slices it off the front).
enum ClipStage {
  planningStory('planning_story', 'Planning story'),
  creatingVoice('creating_voice', 'Creating voice'),
  designingCharacters('designing_characters', 'Designing characters'),
  generatingScenes('generating_scenes', 'Generating scene images'),
  animatingScenes('animating_scenes', 'Animating scenes'),
  assemblingVideo('assembling_video', 'Assembling video'),
  validating('validating', 'Validating');

  const ClipStage(this.key, this.label);
  final String key;
  final String label;
}

class Clip {
  const Clip({
    required this.id,
    required this.take,
    required this.sport,
    required this.tone,
    required this.status,
    this.stageIndex = 0,
    this.error,
    this.durationTarget = 15,
    this.resolution = '720p',
    this.durationSeconds,
    this.videoUrl,
    this.posterUrl,
    this.watermarked = true,
    this.createdAt,
    this.completedAt,
    this.publishes = const [],
    this.currentStep,
    this.isSimulated = false,
    this.script,
    this.scriptApproved = false,
    this.sports = const [],
    this.subjects = const [],
    this.direction = '',
    this.referenceUrl,
    this.creditsCharged = 0,
    this.creditsEdits = 0,
  });

  final String id;
  final String take;
  final String sport;
  final String tone;

  /// "queued" | one of the seven stage keys | "script_ready" | "ready" |
  /// "failed". The stage keys double as the status while that stage runs.
  final String status;
  final int stageIndex;
  final String? error;
  final int durationTarget;
  final String resolution;
  final double? durationSeconds;
  final String? videoUrl;

  /// A real frame from the clip. Null for clips made before posters were
  /// stored, so the caller keeps its gradient fallback.
  final String? posterUrl;
  final bool watermarked;
  final DateTime? createdAt;
  final DateTime? completedAt;
  final List<Publish> publishes;

  /// What the pipeline is doing *right now*, in the user's language. Moves
  /// every few seconds, which is what makes a four-minute wait feel alive.
  final String? currentStep;

  /// A `[mock]` run: real stages, real pacing, nothing generated. Costs
  /// nothing and never touches the allowance.
  final bool isSimulated;
  final Script? script;
  final bool scriptApproved;

  /// Everything the take was tagged with. `sport` above is the first of
  /// these (or what the server inferred) and is kept for older clips.
  final List<String> sports;
  final List<String> subjects;
  final String direction;

  /// The reference photo or video the user attached, if any.
  final String? referenceUrl;

  /// The receipt: what this clip cost once it completed (only successful
  /// videos charge), plus any paid scene edits on top.
  final int creditsCharged;
  final int creditsEdits;

  bool get isReady => status == 'ready';
  bool get hasFailed => status == 'failed';

  /// Waiting on the user (a scene edit is pending review). Not rendering, so
  /// there is nothing to poll — but not failed either.
  bool get isPaused => status == 'paused';

  /// The sport line for a card: every sport picked, or the single one.
  String get sportLabel => sports.isEmpty ? sport : sports.join(' · ');

  /// The script is written and generation is *paused* until the user
  /// approves it. Nothing has been spent yet — this is the money gate.
  bool get awaitingScript => status == 'script_ready' && script != null;

  /// Rendering, in any of its stages.
  bool get inFlight =>
      !isReady && !hasFailed && !awaitingScript && !isPaused;

  /// Ready, but the video URL has not landed (a storage hiccup). Not a
  /// failure — the UI must not call it one.
  bool get isPreparing => isReady && (videoUrl == null || videoUrl!.isEmpty);

  Publish? get latestPublish => publishes.isEmpty ? null : publishes.first;
  bool get isPublished => publishes.any((p) => p.isPublished);

  Publish? get publishedPost {
    for (final p in publishes) {
      if (p.isPublished) return p;
    }
    return null;
  }

  bool get isPublishing => latestPublish?.inFlight ?? false;
  bool get publishFailed => latestPublish?.hasFailed ?? false;

  /// Rounded runtime for display; falls back to the target the user chose.
  int get displaySeconds =>
      (durationSeconds ?? durationTarget.toDouble()).round();

  /// The status line shown on a card, matching `STATUS_LABEL` in `Clips.jsx`.
  String get statusLabel {
    if (status == 'queued') return 'Queued…';
    if (status == 'script_ready') return '📝 Script ready — tap to review';
    if (status == 'paused') return 'Paused — open to continue';
    for (final stage in ClipStage.values) {
      if (stage.key == status) return '${stage.label}…';
    }
    return 'Working…';
  }

  /// The resolution label, mirroring `resolutionLabel()` in
  /// `frontend/src/lib/format.js` — including its even-floored 16:9 height,
  /// so the two clients cannot advertise different specs.
  String get resolutionLabel {
    final width = int.tryParse(resolution.replaceAll(RegExp(r'[^0-9]'), ''));
    if (width == null || width == 0) return '720 × 1280 · 9:16';
    final height = ((width * 16 / 9) / 2).floor() * 2;
    return '$width × $height · 9:16';
  }

  /// The filename the backend uses for a download, reproduced so a shared
  /// file carries the same name the web download would have written.
  String get downloadFilename =>
      'banterclips-${sport.toLowerCase()}-${id.length >= 8 ? id.substring(0, 8) : id}.mp4';

  factory Clip.fromJson(Map<String, dynamic> json) => Clip(
    id: json['id'].toString(),
    take: json['take']?.toString() ?? '',
    sport: json['sport']?.toString() ?? '',
    tone: json['tone']?.toString() ?? '',
    status: json['status']?.toString() ?? 'queued',
    stageIndex: (json['stage_index'] as num?)?.toInt() ?? 0,
    error: json['error'] as String?,
    durationTarget: (json['duration_target'] as num?)?.toInt() ?? 15,
    resolution: json['resolution']?.toString() ?? '720p',
    durationSeconds: (json['duration_seconds'] as num?)?.toDouble(),
    videoUrl: json['video_url'] as String?,
    posterUrl: json['poster_url'] as String?,
    watermarked: json['watermarked'] as bool? ?? true,
    createdAt: DateTime.tryParse(json['created_at']?.toString() ?? ''),
    completedAt: DateTime.tryParse(json['completed_at']?.toString() ?? ''),
    publishes: json['publishes'] is List
        ? (json['publishes'] as List)
              .whereType<Map>()
              .map((e) => Publish.fromJson(Map<String, dynamic>.from(e)))
              .toList()
        : const [],
    currentStep: json['current_step'] as String?,
    isSimulated: json['is_simulated'] as bool? ?? false,
    script: json['script'] is Map
        ? Script.fromJson(Map<String, dynamic>.from(json['script'] as Map))
        : null,
    scriptApproved: json['script_approved'] as bool? ?? false,
    sports: _strings(json['sports']),
    subjects: _strings(json['subjects']),
    direction: json['direction']?.toString() ?? '',
    referenceUrl: json['reference_url'] as String?,
    creditsCharged: (json['credits_charged'] as num?)?.toInt() ?? 0,
    creditsEdits: (json['credits_edits'] as num?)?.toInt() ?? 0,
  );
}

List<String> _strings(dynamic value) =>
    value is List ? value.map((e) => e.toString()).toList() : const [];
