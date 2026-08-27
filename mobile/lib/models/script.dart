/// The plan JSON the backend stores on a clip, as rendered by
/// `frontend/src/components/ScriptView.jsx`.
///
/// This is the one place the API is loosely typed — the pipeline writes the
/// plan, and fields come and go as it evolves. So every field here is
/// optional with a sane fallback, and [Scene.toJson]-style round-tripping is
/// deliberately avoided: edits go back as a sparse `{index, line, action}`
/// patch (see `PATCH /clips/{id}/script`), never as the whole document.
library;

class CastMember {
  const CastMember({required this.id, required this.name, this.look = '', this.wardrobe = ''});

  final String id;
  final String name;
  final String look;
  final String wardrobe;

  factory CastMember.fromJson(Map<String, dynamic> json) => CastMember(
        id: json['id']?.toString() ?? '',
        name: json['name']?.toString() ?? '',
        look: json['look']?.toString() ?? '',
        wardrobe: json['wardrobe']?.toString() ?? '',
      );
}

class Scene {
  const Scene({
    this.seconds = 4,
    this.beat = '',
    this.shotSize = '',
    this.cameraMove = '',
    this.action = '',
    this.beats = '',
    this.expression = '',
    this.line = '',
    this.delivery = '',
    this.speakerId = '',
    this.venue = '',
  });

  final double seconds;
  final String beat;
  final String shotSize;
  final String cameraMove;

  /// What happens on screen. Editable before approval.
  final String action;
  final String beats;
  final String expression;

  /// The spoken line. Empty means a deliberate silent reaction shot — not a
  /// missing value, so the UI says so rather than showing an empty quote.
  final String line;
  final String delivery;
  final String speakerId;
  final String venue;

  bool get isSilent => line.trim().isEmpty;

  /// How many words the shot's duration can actually carry. The backend
  /// trims to this on save; showing it while editing stops the user writing
  /// a paragraph that silently loses its tail.
  int get wordBudget {
    final fit = (seconds * 2.2).floor();
    return fit < 2 ? 2 : fit;
  }

  factory Scene.fromJson(Map<String, dynamic> json) => Scene(
        seconds: (json['seconds'] as num?)?.toDouble() ?? 4,
        beat: json['beat']?.toString() ?? '',
        shotSize: json['shot_size']?.toString() ?? '',
        cameraMove: json['camera_move']?.toString() ?? '',
        action: json['action']?.toString() ?? '',
        beats: json['beats']?.toString() ?? '',
        expression: json['expression']?.toString() ?? '',
        line: json['line']?.toString() ?? '',
        delivery: json['delivery']?.toString() ?? '',
        speakerId: json['speaker_id']?.toString() ?? '',
        venue: json['venue']?.toString() ?? '',
      );

  Scene copyWith({String? line, String? action}) => Scene(
        seconds: seconds,
        beat: beat,
        shotSize: shotSize,
        cameraMove: cameraMove,
        action: action ?? this.action,
        beats: beats,
        expression: expression,
        line: line ?? this.line,
        delivery: delivery,
        speakerId: speakerId,
        venue: venue,
      );
}

class Script {
  const Script({
    this.title = '',
    this.style = '',
    this.cast = const [],
    this.scenes = const [],
    this.storylines = const [],
  });

  final String title;
  final String style;
  final List<CastMember> cast;
  final List<Scene> scenes;

  /// `_context.recent` + `_context.storylines` — the real-world facts the
  /// script was built on. Shown so the user can see it is not invented.
  final List<String> storylines;

  /// Every shot shares one location; the web reads it off the first scene.
  String get venue => scenes.isEmpty ? '' : scenes.first.venue;

  int get totalSeconds =>
      scenes.fold<double>(0, (sum, s) => sum + s.seconds).round();

  CastMember? speakerFor(Scene scene) {
    for (final member in cast) {
      if (member.id == scene.speakerId) return member;
    }
    return null;
  }

  /// The name to print above a line: the cast member's if we know them, the
  /// raw speaker id if not, and "VOICE" as the last resort.
  String speakerLabel(Scene scene) {
    final name = speakerFor(scene)?.name ?? scene.speakerId;
    return (name.isEmpty ? 'VOICE' : name).toUpperCase();
  }

  factory Script.fromJson(Map<String, dynamic> json) {
    final context = json['_context'];
    final storylines = <String>[];
    if (context is Map) {
      for (final key in ['recent', 'storylines']) {
        final value = context[key];
        if (value is List) storylines.addAll(value.map((e) => e.toString()));
      }
    }
    return Script(
      title: json['title']?.toString() ?? '',
      style: json['style']?.toString() ?? '',
      cast: _list(json['cast']).map(CastMember.fromJson).toList(),
      scenes: _list(json['scenes']).map(Scene.fromJson).toList(),
      storylines: storylines,
    );
  }

  Script withScenes(List<Scene> next) => Script(
        title: title,
        style: style,
        cast: cast,
        scenes: next,
        storylines: storylines,
      );

  /// The sparse patch for `PATCH /clips/{id}/script` — only the shots whose
  /// line or action the user actually changed, exactly as `draftEdits()`
  /// builds it in `Studio.jsx`. Sending unchanged shots back would mark the
  /// whole script edited and re-trim lines that were already fitted.
  List<Map<String, dynamic>> diffAgainst(Script original) {
    final edits = <Map<String, dynamic>>[];
    for (var i = 0; i < scenes.length; i++) {
      if (i >= original.scenes.length) break;
      final mine = scenes[i];
      final theirs = original.scenes[i];
      final edit = <String, dynamic>{'index': i};
      if (mine.line != theirs.line) edit['line'] = mine.line;
      if (mine.action != theirs.action) edit['action'] = mine.action;
      if (edit.length > 1) edits.add(edit);
    }
    return edits;
  }
}

List<Map<String, dynamic>> _list(dynamic value) => value is List
    ? value
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList()
    : const [];
