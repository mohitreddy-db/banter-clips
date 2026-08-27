import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../api/errors.dart';
import '../../models/social.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../account/upgrade_sheet.dart';
import 'trending_section.dart';

/// The create screen — part one of the Studio flow in
/// `frontend/src/pages/Studio.jsx`: write a take, sharpen it, choose sport,
/// tone, length and quality, then generate.
///
/// Once a clip exists the flow moves to its own route (`/clip/:id`), which
/// carries script review, live progress and the finished player. On the web
/// those are phases of one page; on a phone they are a screen you push, so
/// the back gesture means what the user expects at every point.
class StudioScreen extends ConsumerStatefulWidget {
  const StudioScreen({super.key});

  @override
  ConsumerState<StudioScreen> createState() => _StudioScreenState();
}

class _StudioScreenState extends ConsumerState<StudioScreen> {
  static const _sports = ['NBA', 'NFL', 'Soccer', 'MLB'];
  static const _tones = [
    ('Funny', '😄', 'Playful roast'),
    ('Savage', '🔪', 'No mercy'),
    ('Hype', '📣', 'Full energy'),
    ('Bold', '💪', 'Fearless claim'),
  ];
  static const _durations = [10, 15, 30];
  static const _resolutions = [('720p', 'HD'), ('1080p', 'Full HD')];

  /// Free tops out at 15 seconds and 720p. Both are enforced server-side too
  /// — these gates exist to explain the limit, not to impose it.
  static const _freeMaxDuration = 15;
  static const _maxTakeLength = 280;
  static const _minTakeLength = 10;

  final _takeController = TextEditingController();

  String _sport = 'NBA';
  String _tone = 'Funny';
  int _duration = 15;
  String _resolution = '720p';

  List<TakeVariation> _variations = const [];

  /// -1 means the user's own wording is selected. A suggestion is only ever
  /// selected, never substituted — their words win by default.
  int _chosen = -1;
  int _round = 0;

  bool _enhancing = false;
  bool _generating = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    // Open on a sport the user actually follows.
    final sports = ref.read(appStateProvider).user?.preferences.sports ?? const [];
    for (final sport in sports) {
      if (_sports.contains(sport)) {
        _sport = sport;
        break;
      }
    }
    _takeController.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _takeController.dispose();
    super.dispose();
  }

  String get _typedTake => _takeController.text.trim();

  bool get _valid =>
      _typedTake.length >= _minTakeLength && _takeController.text.length <= _maxTakeLength;

  /// Whatever will actually be generated: the user's words unless they
  /// picked one of ours.
  String get _activeTake =>
      _chosen >= 0 && _chosen < _variations.length ? _variations[_chosen].take : _typedTake;

  Future<void> _enhance() async {
    if (!_valid || _enhancing) return;
    setState(() {
      _enhancing = true;
      _error = '';
    });
    try {
      final variations = await ref.read(apiClientProvider).enhanceTake(
            take: _typedTake,
            sport: _sport,
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
      if (mounted) {
        setState(() =>
            _error = 'Enhance is unavailable right now (${e.message}). Your take still works.');
      }
    } finally {
      if (mounted) setState(() => _enhancing = false);
    }
  }

  Future<void> _generate() async {
    if (!_valid || _generating) return;
    setState(() {
      _generating = true;
      _error = '';
    });
    try {
      final clip = await ref.read(apiClientProvider).createClip(
            take: _activeTake,
            sport: _sport,
            tone: _tone,
            duration: _duration,
            resolution: _resolution,
          );
      // The in-flight clip appears in the library immediately, exactly as it
      // does on the web.
      ref.read(appStateProvider.notifier).mergeClip(clip);
      if (!mounted) return;
      _reset();
      context.push('/clip/${clip.id}');
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.needsUpgrade) {
        showUpgradeSheet(
          context,
          reason: e.code == ApiCode.limitReached ? UpgradeReason.limit : UpgradeReason.quality,
        );
      } else {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) setState(() => _generating = false);
    }
  }

  void _reset() {
    _takeController.clear();
    setState(() {
      _variations = const [];
      _chosen = -1;
      _round = 0;
      _error = '';
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
      _tone = _tones.any((t) => t.$1 == prompt.tone) ? prompt.tone : _tone;
      if (_durations.contains(prompt.seconds) &&
          (prompt.seconds <= _freeMaxDuration || isCreator)) {
        _duration = prompt.seconds;
      }
    });
    ref.read(apiClientProvider).track('trending_take_used', {
      'sport': _sport,
      'tone': prompt.tone,
      'seconds': prompt.seconds,
    });
    FocusScope.of(context).unfocus();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appStateProvider);
    final isCreator = state.isCreator;
    final length = _takeController.text.length;

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
              title: "What's your sports take?",
              subtitle: "One sentence. We'll do the hook, voice, captions and video.",
            ),
            const SizedBox(height: 22),

            // ---- the take -------------------------------------------------
            TextField(
              controller: _takeController,
              maxLines: 4,
              minLines: 3,
              maxLength: _maxTakeLength,
              // maxLength alone would silently block the 281st character;
              // this lets it through so the counter can turn red and say why.
              maxLengthEnforcement: MaxLengthEnforcement.none,
              textCapitalization: TextCapitalization.sentences,
              style: const TextStyle(
                fontSize: 17,
                height: 1.45,
                fontWeight: FontWeight.w500,
                color: AppColors.text,
              ),
              decoration: InputDecoration(
                hintText: 'Messi is still the GOAT.',
                contentPadding: const EdgeInsets.all(18),
                counterText: '',
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(top: 6, right: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Text(
                    '$length / $_maxTakeLength',
                    style: TextStyle(
                      fontSize: 12,
                      color: length > _maxTakeLength ? AppColors.error : AppColors.muted2,
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),

            // ---- enhance --------------------------------------------------
            Align(
              alignment: Alignment.centerLeft,
              child: _EnhanceButton(
                enabled: _valid && !_enhancing,
                busy: _enhancing,
                hasVariations: _variations.isNotEmpty,
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
                  label: _variations[i].angle.isEmpty ? 'Sharper' : _variations[i].angle,
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
              sport: _sport,
              onUse: (prompt) => _useTrending(prompt, isCreator: isCreator),
            ),
            const SizedBox(height: 24),

            // ---- sport ----------------------------------------------------
            const SectionLabel('SPORT'),
            const SizedBox(height: 10),
            Wrap(
              spacing: 10,
              runSpacing: 10,
              children: [
                for (final sport in _sports)
                  AppChip(
                    label: sport,
                    selected: _sport == sport,
                    onTap: () => setState(() => _sport = sport),
                  ),
              ],
            ),
            const SizedBox(height: 24),

            // ---- tone -----------------------------------------------------
            const SectionLabel('TONE'),
            const SizedBox(height: 10),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 12,
              crossAxisSpacing: 12,
              childAspectRatio: 1.75,
              children: [
                for (final (name, emoji, sub) in _tones)
                  _ToneCard(
                    name: name,
                    emoji: emoji,
                    sub: sub,
                    selected: _tone == name,
                    onTap: () => setState(() => _tone = name),
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
                  Builder(builder: (context) {
                    final locked = seconds > _freeMaxDuration && !isCreator;
                    return AppChip(
                      label: '${seconds}s',
                      selected: _duration == seconds,
                      locked: locked,
                      trailing: locked ? const CreatorPill() : null,
                      onTap: () => locked
                          ? showUpgradeSheet(context, reason: UpgradeReason.duration)
                          : setState(() => _duration = seconds),
                    );
                  }),
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
                  Builder(builder: (context) {
                    final locked = key == '1080p' && !isCreator;
                    return AppChip(
                      label: '$key · $sub',
                      selected: _resolution == key,
                      locked: locked,
                      trailing: locked ? const CreatorPill() : null,
                      onTap: () => locked
                          ? showUpgradeSheet(context, reason: UpgradeReason.quality)
                          : setState(() => _resolution = key),
                    );
                  }),
              ],
            ),
            const SizedBox(height: 20),

            // ---- allowance ------------------------------------------------
            AppPanel(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
              child: Row(
                children: [
                  const Icon(Icons.bolt_rounded, size: 17, color: AppColors.cyan),
                  const SizedBox(width: 9),
                  Expanded(
                    child: Text.rich(
                      TextSpan(
                        style: const TextStyle(fontSize: 13, color: AppColors.muted, height: 1.4),
                        children: [
                          TextSpan(
                            text: '${state.left}',
                            style: const TextStyle(
                              fontWeight: FontWeight.w700,
                              color: AppColors.text,
                            ),
                          ),
                          TextSpan(text: ' of ${state.limit} monthly videos left'),
                          const TextSpan(text: ' · failures are free'),
                        ],
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
              label: '🪄  Generate BanterClip',
              height: 56,
              fontSize: 17,
              loading: _generating,
              onPressed: _valid ? _generate : null,
            ),
            const SizedBox(height: 10),
            Text(
              'Hot Take format · cinematic scenes · ${_duration}s vertical MP4 · $_resolution',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 12, color: AppColors.muted2),
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
              for (final clip in state.clips.take(3))
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: AppPanel(
                    onTap: () => context.push('/clip/${clip.id}'),
                    child: Row(
                      children: [
                        Container(
                          width: 30,
                          height: 50,
                          decoration: BoxDecoration(
                            gradient: AppColors.thumbFor(clip.id),
                            borderRadius: BorderRadius.circular(7),
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
                                '${clip.sport} · ${clip.tone}'
                                '${clip.isReady ? (clip.isPublished ? ' · published' : '') : ' · ${clip.status}'}',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: clip.hasFailed ? AppColors.error : AppColors.muted,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const Icon(Icons.chevron_right_rounded,
                            size: 20, color: AppColors.muted2),
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

/// The ✨ button. Offered, never imposed — pressing it adds options below the
/// take box and leaves what was typed untouched.
class _EnhanceButton extends StatelessWidget {
  const _EnhanceButton({
    required this.enabled,
    required this.busy,
    required this.hasVariations,
    required this.onPressed,
  });

  final bool enabled;
  final bool busy;
  final bool hasVariations;
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
                color: enabled ? AppColors.cyan.withValues(alpha: 0.45) : AppColors.border,
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
                          ? 'Enhance again'
                          : 'Enhance take',
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
                  selected ? Icons.radio_button_checked : Icons.radio_button_unchecked,
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
              Text(hint!, style: const TextStyle(fontSize: 11.5, color: AppColors.muted)),
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
        padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 8),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(emoji, style: const TextStyle(fontSize: 22)),
            const SizedBox(height: 5),
            Text(
              name,
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w700,
                color: selected ? AppColors.cyan : AppColors.text,
              ),
            ),
            const SizedBox(height: 2),
            Text(sub, style: const TextStyle(fontSize: 11, color: AppColors.muted)),
          ],
        ),
      );
}
