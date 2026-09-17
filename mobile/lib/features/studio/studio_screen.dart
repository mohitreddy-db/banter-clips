import 'dart:io';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:image_picker/image_picker.dart';

import '../../api/errors.dart';
import '../../models/catalog.dart' as catalog;
import '../../models/social.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../account/top_up_sheet.dart';
import '../account/upgrade_sheet.dart';
import 'trending_section.dart';

/// The create screen — part one of the Studio flow in
/// `frontend/src/pages/Studio.jsx`, section for section: the take, what
/// happens, a reference, enhance, trending, sports, who is in it, style,
/// length, quality, the price line, then generate.
///
/// Once a clip exists the flow moves to its own route (`/clip/:id`), which
/// carries script review, live progress and the finished player. On the web
/// those are phases of one page; on a phone they are a screen you push, so
/// the back gesture means what the user expects at every point.
///
/// Nothing here that the backend does not consume: `ClipCreate` is the
/// contract, and every control on this screen maps to one of its fields.
class StudioScreen extends ConsumerStatefulWidget {
  const StudioScreen({super.key});

  @override
  ConsumerState<StudioScreen> createState() => _StudioScreenState();
}

class _StudioScreenState extends ConsumerState<StudioScreen> {
  static const _durations = [10, 15, 30];
  static const _resolutions = [('720p', 'HD'), ('1080p', 'Full HD')];

  /// Free tops out at 15 seconds, 720p and 280 characters. All enforced
  /// server-side too — these gates exist to explain the limit, not to
  /// impose it.
  static const _freeMaxDuration = 15;
  static const _freeMaxTake = 280;
  static const _creatorMaxTake = 500;
  static const _minTakeLength = 10;
  static const _maxDirection = 400;
  static const _maxSports = 4;
  static const _maxSubjects = 8;
  static const _maxReferenceBytes = 15 * 1024 * 1024;

  final _takeController = TextEditingController();
  final _directionController = TextEditingController();
  final _subjectController = TextEditingController();
  final _picker = ImagePicker();

  List<String> _sports = const [];
  List<String> _subjects = const [];
  String _tone = 'Funny';
  int _duration = 15;
  String _resolution = '720p';
  XFile? _reference;
  bool _referenceIsVideo = false;
  String _lastImportedPrompt = '';

  List<TakeVariation> _variations = const [];

  /// -1 means the user's own wording is selected. A suggestion is only ever
  /// selected, never substituted — their words win by default.
  int _chosen = -1;
  int _round = 0;

  bool _enhancing = false;
  bool _generating = false;
  bool _uploading = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _takeController.addListener(() => setState(() {}));
    _subjectController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _takeController.dispose();
    _directionController.dispose();
    _subjectController.dispose();
    super.dispose();
  }

  bool get _isCreator => ref.read(appStateProvider).isCreator;
  int get _maxTakeLength => _isCreator ? _creatorMaxTake : _freeMaxTake;

  String get _typedTake => _takeController.text.trim();

  bool get _valid =>
      _typedTake.length >= _minTakeLength &&
      _takeController.text.length <= _maxTakeLength;

  /// Whatever will actually be generated: the user's words unless they
  /// picked one of ours.
  String get _activeTake => _chosen >= 0 && _chosen < _variations.length
      ? _variations[_chosen].take
      : _typedTake;

  /// The sport the trending feed and enhance are keyed on: the first one
  /// picked, else the first the user follows, else Soccer — as on the web.
  String get _leadSport {
    if (_sports.isNotEmpty) return _sports.first;
    final followed =
        ref.read(appStateProvider).user?.preferences.sports ?? const [];
    for (final sport in followed) {
      if (catalog.isKnownSport(sport)) return sport;
    }
    return 'Soccer';
  }

  Future<void> _enhance() async {
    if (!_valid || _enhancing) return;
    setState(() {
      _enhancing = true;
      _error = '';
    });
    try {
      final variations = await ref
          .read(apiClientProvider)
          .enhanceTake(
            take: _typedTake,
            sport: _leadSport,
            tone: _tone,
            round: _round,
          );
      if (!mounted) return;
      setState(() {
        if (variations.isEmpty) {
          _error = "Couldn't find a better angle — your take is good as is.";
        } else {
          _variations = variations;
          _chosen = -1; // never auto-select
          _round++;
        }
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.needsCredits) {
        showTopUpSheet(context, needed: _enhanceCost);
      } else {
        setState(
          () => _error =
              'Enhance is unavailable right now (${e.message}). Your take still works.',
        );
      }
    } finally {
      if (mounted) setState(() => _enhancing = false);
      // Enhance is a paid action; the balance moved.
      ref.read(appStateProvider.notifier).refreshUsage();
    }
  }

  int get _enhanceCost => ref.read(appStateProvider).prices.enhanceTake;

  Future<void> _generate() async {
    if (!_valid || _generating) return;
    final state = ref.read(appStateProvider);
    final price = state.videoPrice(_duration, _resolution);
    // The server says no too, but a sheet before the round-trip is the
    // honest experience: the price was on screen the whole time.
    if (state.credits < price) {
      showTopUpSheet(context, needed: price);
      return;
    }
    setState(() {
      _generating = true;
      _error = '';
    });
    try {
      final api = ref.read(apiClientProvider);
      String? referenceKey;
      final reference = _reference;
      if (reference != null) {
        setState(() => _uploading = true);
        referenceKey = await api.uploadReference(
          File(reference.path),
          contentType: _referenceIsVideo ? 'video/mp4' : 'image/jpeg',
        );
        if (mounted) setState(() => _uploading = false);
      }
      final clip = await api.createClip(
        take: _activeTake,
        sports: _sports,
        subjects: _subjects,
        tone: _tone,
        duration: _duration,
        resolution: _resolution,
        direction: _directionController.text.trim(),
        referenceKey: referenceKey,
      );
      // The in-flight clip appears in the library immediately, exactly as it
      // does on the web — and the reservation moved the balance.
      ref.read(appStateProvider.notifier).mergeClip(clip);
      ref.read(appStateProvider.notifier).refreshUsage();
      if (!mounted) return;
      _reset();
      context.push('/clip/${clip.id}');
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.needsCredits) {
        showTopUpSheet(context, needed: price);
      } else if (e.needsUpgrade) {
        showUpgradeSheet(
          context,
          reason: _duration > _freeMaxDuration
              ? UpgradeReason.duration
              : UpgradeReason.quality,
        );
      } else {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) {
        setState(() {
          _generating = false;
          _uploading = false;
        });
      }
    }
  }

  void _reset() {
    _takeController.clear();
    _directionController.clear();
    _subjectController.clear();
    setState(() {
      _variations = const [];
      _chosen = -1;
      _round = 0;
      _error = '';
      _subjects = const [];
      _reference = null;
    });
  }

  /// A trending suggestion fills the take box as though it were typed, and
  /// nudges tone and length to fit — without ever selecting a length the
  /// user's plan does not allow.
  void _useTrending(TrendingPrompt prompt, {required bool isCreator}) {
    _takeController.text = prompt.take;
    setState(() {
      _variations = const [];
      _chosen = -1;
      if (catalog.isKnownTone(prompt.tone)) _tone = prompt.tone;
      if (_durations.contains(prompt.seconds) &&
          (prompt.seconds <= _freeMaxDuration || isCreator)) {
        _duration = prompt.seconds;
      }
    });
    ref.read(apiClientProvider).track('trending_take_used', {
      'sport': _leadSport,
      'tone': prompt.tone,
      'seconds': prompt.seconds,
    });
    FocusScope.of(context).unfocus();
  }

  /// Opened from the Viral screen (or a share link) as
  /// `/studio?prompt=…&tone=…&seconds=…&sport=…`.
  void _importFromQuery(Uri uri, {required bool isCreator}) {
    final imported = uri.queryParameters['prompt'] ?? '';
    if (imported.isEmpty || imported == _lastImportedPrompt) return;
    _lastImportedPrompt = imported;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      _takeController.text = imported.length > _maxTakeLength
          ? imported.substring(0, _maxTakeLength)
          : imported;
      final sport = uri.queryParameters['sport'];
      final tone = uri.queryParameters['tone'];
      final seconds = int.tryParse(uri.queryParameters['seconds'] ?? '');
      setState(() {
        _variations = const [];
        _chosen = -1;
        if (catalog.isKnownSport(sport)) _sports = [sport!];
        if (catalog.isKnownTone(tone)) _tone = tone!;
        if (seconds != null &&
            _durations.contains(seconds) &&
            (seconds <= _freeMaxDuration || isCreator)) {
          _duration = seconds;
        }
      });
    });
  }

  void _toggleSport(String sport) => setState(() {
    if (_sports.contains(sport)) {
      _sports = _sports.where((s) => s != sport).toList();
    } else if (_sports.length < _maxSports) {
      _sports = [..._sports, sport];
    }
  });

  void _addSubject(String raw) {
    final value = raw.trim().replaceAll(RegExp(r',$'), '').trim();
    _subjectController.clear();
    if (value.isEmpty || _subjects.contains(value)) return;
    if (_subjects.length >= _maxSubjects) return;
    setState(() => _subjects = [..._subjects, value]);
  }

  Future<void> _pickReference(bool video) async {
    final file = video
        ? await _picker.pickVideo(source: ImageSource.gallery)
        : await _picker.pickImage(source: ImageSource.gallery, imageQuality: 92);
    if (file == null || !mounted) return;
    final size = await file.length();
    if (!mounted) return;
    if (size > _maxReferenceBytes) {
      setState(() => _error = 'Reference must be 15 MB or smaller.');
      return;
    }
    setState(() {
      _reference = file;
      _referenceIsVideo = video;
      _error = '';
    });
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appStateProvider);
    final isCreator = state.isCreator;
    final maxTake = isCreator ? _creatorMaxTake : _freeMaxTake;
    final length = _takeController.text.length;
    final overLimit = length > maxTake;
    final price = state.videoPrice(_duration, _resolution);
    final short = state.credits < price;
    _importFromQuery(GoRouterState.of(context).uri, isCreator: isCreator);

    final suggestions = catalog
        .subjectSuggestions(
          _sports.isNotEmpty
              ? _sports
              : (state.user?.preferences.sports ?? const []),
          players: true,
          limit: 6,
        )
        .where((s) => !_subjects.contains(s))
        .toList();

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          children: [
            const ScreenHeader(
              badge: '⚡ NEW CLIP',
              title: 'Build your banter',
              subtitle:
                  'Simple choices in. A production-ready video prompt out.',
            ),
            const SizedBox(height: 22),

            // ---- the take -------------------------------------------------
            const SectionLabel('WHAT DO YOU WANT TO SAY?'),
            const SizedBox(height: 10),
            TextField(
              controller: _takeController,
              maxLines: 4,
              minLines: 3,
              maxLength: maxTake,
              // maxLength alone would silently block the next character;
              // this lets it through so the counter can turn red and say why.
              maxLengthEnforcement: MaxLengthEnforcement.none,
              textCapitalization: TextCapitalization.sentences,
              style: const TextStyle(
                fontSize: 17,
                height: 1.45,
                fontWeight: FontWeight.w500,
                color: AppColors.text,
              ),
              decoration: const InputDecoration(
                hintText: 'Messi is still the GOAT.',
                contentPadding: EdgeInsets.all(18),
                counterText: '',
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(top: 6, right: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  InkWell(
                    onTap: !isCreator && overLimit
                        ? () => showUpgradeSheet(
                            context,
                            reason: UpgradeReason.takeLength,
                          )
                        : null,
                    child: Text(
                      '$length / $maxTake'
                      '${!isCreator && overLimit ? ' · up to $_creatorMaxTake on Creator →' : ''}',
                      style: TextStyle(
                        fontSize: 12,
                        color: overLimit ? AppColors.error : AppColors.muted2,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 18),

            // ---- what happens ---------------------------------------------
            const _LabelWithHint(
              'WHAT HAPPENS?',
              'optional · describe the setting or action',
            ),
            const SizedBox(height: 10),
            TextField(
              controller: _directionController,
              minLines: 2,
              maxLines: 4,
              maxLength: _maxDirection,
              textCapitalization: TextCapitalization.sentences,
              decoration: const InputDecoration(
                hintText:
                    'Press room after the derby. The manager stays calm while the mascot celebrates behind him.',
                counterText: '',
              ),
            ),
            const SizedBox(height: 20),

            // ---- reference -----------------------------------------------
            const _LabelWithHint(
              'REFERENCE PHOTO OR VIDEO',
              'optional · JPEG or MP4 · up to 15 MB',
            ),
            const SizedBox(height: 10),
            AppPanel(
              onTap: () => _pickReference(false),
              child: Row(
                children: [
                  Icon(
                    _reference == null
                        ? Icons.add_photo_alternate_outlined
                        : Icons.check_circle_rounded,
                    color: _reference == null ? AppColors.cyan : AppColors.green,
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      _reference == null
                          ? '+ Choose a reference'
                          : '${_referenceIsVideo ? 'Video' : 'Photo'} · ${_reference!.name}',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        color: _reference == null
                            ? AppColors.muted
                            : AppColors.text,
                      ),
                    ),
                  ),
                  if (_reference == null)
                    IconButton(
                      tooltip: 'Choose a video',
                      onPressed: () => _pickReference(true),
                      icon: const Icon(Icons.video_library_outlined),
                    )
                  else
                    IconButton(
                      tooltip: 'Remove reference',
                      onPressed: () => setState(() => _reference = null),
                      icon: const Icon(Icons.close_rounded),
                    ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // ---- enhance --------------------------------------------------
            Align(
              alignment: Alignment.centerLeft,
              child: _EnhanceButton(
                enabled: _valid && !_enhancing,
                busy: _enhancing,
                hasVariations: _variations.isNotEmpty,
                cost: state.prices.enhanceTake,
                onPressed: _enhance,
              ),
            ),
            if (_enhancing) ...[
              const SizedBox(height: 12),
              const Skeleton(height: 74),
              const SizedBox(height: 10),
              const Skeleton(height: 74),
            ],
            if (!_enhancing && _variations.isNotEmpty) ...[
              const SizedBox(height: 12),
              _TakeOption(
                label: 'Your take',
                text: _typedTake,
                selected: _chosen == -1,
                onTap: () => setState(() => _chosen = -1),
              ),
              for (var i = 0; i < _variations.length; i++) ...[
                const SizedBox(height: 10),
                _TakeOption(
                  label: _variations[i].angle.isEmpty
                      ? 'Sharper'
                      : _variations[i].angle,
                  badge: '✨',
                  text: _variations[i].take,
                  hint: _variations[i].why,
                  selected: _chosen == i,
                  onTap: () => setState(() => _chosen = i),
                ),
              ],
            ],
            const SizedBox(height: 24),

            // ---- trending -------------------------------------------------
            TrendingSection(
              sport: _leadSport,
              onUse: (prompt) => _useTrending(prompt, isCreator: isCreator),
            ),
            const SizedBox(height: 24),

            // ---- sport (multi) --------------------------------------------
            _LabelWithHint(
              'SPORT',
              _sports.isEmpty
                  ? "optional · we'll work it out from your take"
                  : 'optional · pick more than one to cross them over',
              trailing: _sports.isEmpty
                  ? null
                  : TextAction(
                      label: 'Clear',
                      fontSize: 12,
                      color: AppColors.muted,
                      onPressed: () => setState(() => _sports = const []),
                    ),
            ),
            const SizedBox(height: 10),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final sport in catalog.sports)
                  AppChip(
                    label: '${sport.emoji} ${sport.key}',
                    selected: _sports.contains(sport.key),
                    onTap: () => _toggleSport(sport.key),
                  ),
              ],
            ),
            const SizedBox(height: 24),

            // ---- who is in it ---------------------------------------------
            const _LabelWithHint(
              'WHO IS IN IT?',
              'optional · anyone you add will be in the video',
            ),
            const SizedBox(height: 10),
            if (_subjects.isNotEmpty) ...[
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final subject in _subjects)
                    AppChip(
                      label: '$subject  ×',
                      selected: true,
                      onTap: () => setState(
                        () => _subjects = _subjects
                            .where((s) => s != subject)
                            .toList(),
                      ),
                    ),
                ],
              ),
              const SizedBox(height: 10),
            ],
            TextField(
              controller: _subjectController,
              textCapitalization: TextCapitalization.words,
              textInputAction: TextInputAction.done,
              onSubmitted: _addSubject,
              onEditingComplete: () => _addSubject(_subjectController.text),
              decoration: InputDecoration(
                hintText: 'Add a team or player — Arsenal, Mbappé, LeBron…',
                prefixIcon: const Icon(Icons.groups_2_outlined),
                suffixIcon: _subjectController.text.trim().isEmpty
                    ? null
                    : IconButton(
                        icon: const Icon(
                          Icons.add_rounded,
                          color: AppColors.cyan,
                        ),
                        onPressed: () => _addSubject(_subjectController.text),
                      ),
              ),
            ),
            if (suggestions.isNotEmpty) ...[
              const SizedBox(height: 8),
              Wrap(
                spacing: 7,
                runSpacing: 7,
                children: [
                  for (final suggestion in suggestions)
                    AppChip(
                      label: '+ $suggestion',
                      dashed: true,
                      onTap: () => _addSubject(suggestion),
                    ),
                ],
              ),
            ],
            const SizedBox(height: 24),

            // ---- style (tone) ---------------------------------------------
            const SectionLabel('STYLE'),
            const SizedBox(height: 10),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.6,
              children: [
                for (final tone in catalog.tones)
                  _ToneCard(
                    name: tone.key,
                    emoji: tone.emoji,
                    sub: tone.sub,
                    selected: _tone == tone.key,
                    onTap: () => setState(() => _tone = tone.key),
                  ),
              ],
            ),
            const SizedBox(height: 24),

            // ---- length ---------------------------------------------------
            const SectionLabel('LENGTH'),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final seconds in _durations)
                  Builder(
                    builder: (context) {
                      final locked = seconds > _freeMaxDuration && !isCreator;
                      return AppChip(
                        label: '${seconds}s',
                        selected: _duration == seconds,
                        locked: locked,
                        trailing: locked ? const CreatorPill() : null,
                        onTap: () => locked
                            ? showUpgradeSheet(
                                context,
                                reason: UpgradeReason.duration,
                              )
                            : setState(() => _duration = seconds),
                      );
                    },
                  ),
              ],
            ),
            const SizedBox(height: 24),

            // ---- quality --------------------------------------------------
            const SectionLabel('QUALITY'),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final (key, sub) in _resolutions)
                  Builder(
                    builder: (context) {
                      final locked = key == '1080p' && !isCreator;
                      return AppChip(
                        label: '$key · $sub',
                        selected: _resolution == key,
                        locked: locked,
                        trailing: locked ? const CreatorPill() : null,
                        onTap: () => locked
                            ? showUpgradeSheet(
                                context,
                                reason: UpgradeReason.quality,
                              )
                            : setState(() => _resolution = key),
                      );
                    },
                  ),
              ],
            ),
            const SizedBox(height: 20),

            // ---- price line -----------------------------------------------
            AppPanel(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Padding(
                        padding: EdgeInsets.only(top: 1),
                        child: Icon(
                          Icons.bolt_rounded,
                          size: 17,
                          color: AppColors.cyan,
                        ),
                      ),
                      const SizedBox(width: 9),
                      Expanded(
                        child: Text.rich(
                          TextSpan(
                            style: const TextStyle(
                              fontSize: 13,
                              color: AppColors.muted,
                              height: 1.45,
                            ),
                            children: [
                              const TextSpan(text: 'This video: '),
                              TextSpan(
                                text: '$price credits',
                                style: const TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.text,
                                ),
                              ),
                              const TextSpan(text: ' · you have '),
                              TextSpan(
                                text: '${state.credits}',
                                style: TextStyle(
                                  fontWeight: FontWeight.w700,
                                  color: short
                                      ? AppColors.error
                                      : AppColors.text,
                                ),
                              ),
                              const TextSpan(
                                text:
                                    ' · charged only when your video completes',
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Align(
                    alignment: Alignment.centerRight,
                    child: TextAction(
                      label: '+ Top up credits',
                      fontSize: 13,
                      onPressed: () => showTopUpSheet(
                        context,
                        needed: short ? price : 0,
                      ),
                    ),
                  ),
                ],
              ),
            ),

            if (_error.isNotEmpty) ...[
              const SizedBox(height: 14),
              Notice.error(_error),
            ],
            const SizedBox(height: 18),

            GradButton(
              label: '🪄  Build My Banter',
              height: 56,
              fontSize: 17,
              loading: _generating,
              onPressed: _valid ? _generate : null,
            ),
            const SizedBox(height: 10),
            Text(
              _generating
                  ? (_uploading ? 'Uploading reference…' : 'Starting…')
                  : 'Hot Take format · cinematic scenes · ${_duration}s vertical MP4 · $_resolution',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 12,
                color: _generating ? AppColors.cyan : AppColors.muted2,
              ),
            ),

            // ---- recent ---------------------------------------------------
            if (state.clips.isNotEmpty) ...[
              const SizedBox(height: 28),
              SectionLabel(
                'RECENT CLIPS',
                trailing: TextAction(
                  label: 'View all →',
                  fontSize: 12.5,
                  onPressed: () => context.go('/clips'),
                ),
              ),
              const SizedBox(height: 10),
              for (final clip in state.clips.take(4))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: AppPanel(
                    onTap: () => context.push('/clip/${clip.id}'),
                    child: Row(
                      children: [
                        ClipRRect(
                          borderRadius: BorderRadius.circular(7),
                          child: SizedBox(
                            width: 34,
                            height: 58,
                            child: Stack(
                              fit: StackFit.expand,
                              children: [
                                // A real frame from the clip. The gradient
                                // stays as the fallback for clips made
                                // before posters were stored.
                                DecoratedBox(
                                  decoration: BoxDecoration(
                                    gradient: AppColors.thumbFor(clip.id),
                                  ),
                                ),
                                if ((clip.posterUrl ?? '').isNotEmpty)
                                  CachedNetworkImage(
                                    imageUrl: clip.posterUrl!,
                                    fit: BoxFit.cover,
                                    fadeInDuration: const Duration(
                                      milliseconds: 180,
                                    ),
                                    errorWidget: (_, __, ___) =>
                                        const SizedBox.shrink(),
                                  ),
                              ],
                            ),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(
                                clip.take,
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: const TextStyle(
                                  fontSize: 13,
                                  fontWeight: FontWeight.w500,
                                  color: AppColors.text,
                                ),
                              ),
                              const SizedBox(height: 3),
                              Text(
                                '${clip.sportLabel} · ${clip.tone}'
                                '${clip.isReady ? (clip.isPublished ? ' · published' : '') : ' · ${clip.status}'}',
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: clip.hasFailed
                                      ? AppColors.error
                                      : AppColors.muted,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Icon(
                          Icons.chevron_right_rounded,
                          size: 20,
                          color: AppColors.muted2,
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ],
        ),
      ),
    );
  }
}

/// A section label with the web's small grey hint beside it.
class _LabelWithHint extends StatelessWidget {
  const _LabelWithHint(this.label, this.hint, {this.trailing});

  final String label;
  final String hint;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.end,
    children: [
      Expanded(
        child: Wrap(
          crossAxisAlignment: WrapCrossAlignment.end,
          spacing: 8,
          runSpacing: 2,
          children: [
            SectionLabel(label),
            Text(
              hint,
              style: const TextStyle(fontSize: 11.5, color: AppColors.muted2),
            ),
          ],
        ),
      ),
      if (trailing != null) trailing!,
    ],
  );
}

/// The ✨ button. Offered, never imposed — pressing it adds options below the
/// take box and leaves what was typed untouched.
class _EnhanceButton extends StatelessWidget {
  const _EnhanceButton({
    required this.enabled,
    required this.busy,
    required this.hasVariations,
    required this.cost,
    required this.onPressed,
  });

  final bool enabled;
  final bool busy;
  final bool hasVariations;
  final int cost;
  final VoidCallback onPressed;

  @override
  Widget build(BuildContext context) => Material(
    color: AppColors.cyanWash(0.08),
    borderRadius: BorderRadius.circular(AppTheme.radiusPill),
    child: InkWell(
      onTap: enabled ? onPressed : null,
      borderRadius: BorderRadius.circular(AppTheme.radiusPill),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 11),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppTheme.radiusPill),
          border: Border.all(
            color: enabled
                ? AppColors.cyan.withValues(alpha: 0.45)
                : AppColors.border,
          ),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (busy)
              const InlineSpinner(size: 14)
            else
              const Text('✨', style: TextStyle(fontSize: 14)),
            const SizedBox(width: 9),
            Text(
              busy
                  ? 'Finding sharper angles…'
                  : hasVariations
                  ? 'Enhance again · $cost credit${cost == 1 ? '' : 's'}'
                  : 'Enhance take · $cost credit${cost == 1 ? '' : 's'}',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w700,
                color: enabled ? AppColors.cyan : AppColors.muted2,
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

/// One selectable wording — the user's own, or a suggested variation.
class _TakeOption extends StatelessWidget {
  const _TakeOption({
    required this.label,
    required this.text,
    required this.selected,
    required this.onTap,
    this.hint,
    this.badge,
  });

  final String label;
  final String text;
  final bool selected;
  final VoidCallback onTap;
  final String? hint;
  final String? badge;

  @override
  Widget build(BuildContext context) => AppPanel(
    onTap: onTap,
    color: selected ? AppColors.cyanWash(0.10) : Colors.transparent,
    borderColor: selected ? AppColors.cyan : AppColors.border,
    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 13),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            if (badge != null) ...[
              Text(badge!, style: const TextStyle(fontSize: 11)),
              const SizedBox(width: 5),
            ],
            Text(
              label.toUpperCase(),
              style: TextStyle(
                fontSize: 10,
                fontWeight: FontWeight.w800,
                letterSpacing: 0.7,
                color: selected ? AppColors.cyan : AppColors.muted2,
              ),
            ),
            const Spacer(),
            Icon(
              selected
                  ? Icons.radio_button_checked
                  : Icons.radio_button_unchecked,
              size: 16,
              color: selected ? AppColors.cyan : AppColors.muted2,
            ),
          ],
        ),
        const SizedBox(height: 6),
        Text(
          text,
          style: const TextStyle(
            fontSize: 14,
            height: 1.45,
            fontWeight: FontWeight.w600,
            color: AppColors.text,
          ),
        ),
        if (hint != null && hint!.isNotEmpty) ...[
          const SizedBox(height: 5),
          Text(
            hint!,
            style: const TextStyle(fontSize: 11.5, color: AppColors.muted),
          ),
        ],
      ],
    ),
  );
}

class _ToneCard extends StatelessWidget {
  const _ToneCard({
    required this.name,
    required this.emoji,
    required this.sub,
    required this.selected,
    required this.onTap,
  });

  final String name;
  final String emoji;
  final String sub;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => AppPanel(
    onTap: onTap,
    color: selected ? AppColors.cyanWash(0.08) : AppColors.surface,
    borderColor: selected ? AppColors.cyan : AppColors.border,
    padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(emoji, style: const TextStyle(fontSize: 22)),
        const SizedBox(height: 4),
        Text(
          name,
          style: TextStyle(
            fontSize: 14.5,
            fontWeight: FontWeight.w700,
            color: selected ? AppColors.cyan : AppColors.text,
          ),
        ),
        const SizedBox(height: 2),
        Text(
          sub,
          style: const TextStyle(fontSize: 11, color: AppColors.muted),
        ),
      ],
    ),
  );
}
