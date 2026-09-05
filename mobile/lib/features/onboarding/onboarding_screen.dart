import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../api/errors.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';
import '../account/instagram_connect.dart';

/// Onboarding — the port of `frontend/src/pages/Onboarding.jsx`.
///
/// Four steps, all skippable: sports, favourite teams and players, what kind
/// of creator you are, and connecting Instagram. Each step saves as it is
/// completed (so nothing is lost if the app is killed, or if the Instagram
/// consent screen takes the user out to the browser and back); the
/// `onboarding_completed` flag is only set at the very end.
///
/// The web's fifth step — choosing a plan — is deliberately absent. Selling a
/// subscription inside the app means store billing (Apple 3.1.1); v1 points
/// at the website instead. See `AccountScreen`.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  static const _totalSteps = 4;

  /// The four sports the pipeline actually supports today. The web shows
  /// eight and greys out the rest; on a phone that is four dead tiles taking
  /// up a screen, so only the live ones appear.
  static const _sports = [
    ('NBA', '🏀'),
    ('NFL', '🏈'),
    ('Soccer', '⚽'),
    ('MLB', '⚾'),
  ];

  static const _roles = [
    ('Sports Fan', '🙌'),
    ('Creator', '🎬'),
    ('Podcaster', '🎙'),
    ('Media Company', '📺'),
    ('Fantasy Creator', '📊'),
  ];

  int _step = 1;
  late List<String> _sportsPicked;
  late List<String> _teams;
  late List<String> _players;
  String? _role;

  final _teamInput = TextEditingController();
  final _playerInput = TextEditingController();
  bool _busy = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    // Pre-fill from whatever is already saved — this screen doubles as
    // "edit my preferences", reached from Account.
    final prefs = ref.read(appStateProvider).user?.preferences;
    _sportsPicked = [...?prefs?.sports];
    _teams = [...?prefs?.teams];
    _players = [...?prefs?.players];
    _role = prefs?.role;
  }

  @override
  void dispose() {
    _teamInput.dispose();
    _playerInput.dispose();
    super.dispose();
  }

  /// Save just what this step collected. Best-effort: a failed save must not
  /// trap the user on a step, and the final save repeats everything anyway.
  void _persistStep() {
    final notifier = ref.read(appStateProvider.notifier);
    switch (_step) {
      case 1:
        notifier.savePreferences(sports: _sportsPicked).catchError((_) {});
      case 2:
        notifier
            .savePreferences(teams: _teams, players: _players)
            .catchError((_) {});
      case 3:
        if (_role != null) {
          notifier.savePreferences(role: _role).catchError((_) {});
        }
    }
  }

  Future<void> _finish() async {
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      await ref
          .read(appStateProvider.notifier)
          .savePreferences(
            sports: _sportsPicked,
            teams: _teams,
            players: _players,
            role: _role,
            onboardingCompleted: true,
          );
      if (mounted) context.go('/studio');
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  void _next() {
    _persistStep();
    if (_step >= _totalSteps) {
      _finish();
    } else {
      setState(() => _step++);
    }
  }

  void _addTag(TextEditingController controller, List<String> into) {
    final value = controller.text.trim();
    if (value.isEmpty || into.contains(value)) {
      controller.clear();
      return;
    }
    setState(() {
      into.add(value);
      controller.clear();
    });
  }

  @override
  Widget build(BuildContext context) {
    const titles = {
      1: 'What do you follow?',
      2: 'Favourite teams & players',
      3: 'What kind of creator are you?',
      4: 'Connect Instagram',
    };
    const subtitles = {
      1: 'Your Studio opens on these.',
      2: 'We name them in your clips when they fit.',
      3: 'It shapes the tone we suggest.',
      4: 'Optional — you can do this later from Account.',
    };
    final optional = _step >= 2;

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 0),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'STEP $_step OF $_totalSteps${optional ? ' · OPTIONAL' : ''}',
                    style: const TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w700,
                      letterSpacing: 1.4,
                      color: AppColors.muted,
                    ),
                  ),
                  const SizedBox(height: 10),
                  ClipRRect(
                    borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                    child: Stack(
                      children: [
                        Container(height: 6, color: AppColors.panel),
                        AnimatedFractionallySizedBox(
                          duration: const Duration(milliseconds: 250),
                          widthFactor: _step / _totalSteps,
                          child: Container(
                            height: 6,
                            decoration: const BoxDecoration(
                              gradient: AppColors.gradient,
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 22),
                  Text(
                    titles[_step]!,
                    style: Theme.of(context).textTheme.displaySmall,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    subtitles[_step]!,
                    style: Theme.of(context).textTheme.bodyMedium,
                  ),
                ],
              ),
            ),
            Expanded(
              child: SingleChildScrollView(
                padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
                child: switch (_step) {
                  1 => _sportsStep(),
                  2 => _tagsStep(),
                  3 => _roleStep(),
                  _ => const _InstagramStep(),
                },
              ),
            ),
            if (_error.isNotEmpty)
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 0, 20, 10),
                child: Notice.error(_error),
              ),
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
              child: Row(
                children: [
                  if (_step > 1)
                    GhostButton(
                      label: 'Back',
                      expand: false,
                      onPressed: () => setState(() => _step--),
                    ),
                  if (_step > 1) const SizedBox(width: 10),
                  Expanded(
                    child: GradButton(
                      label: _step == _totalSteps ? "I'm ready" : 'Continue',
                      loading: _busy,
                      onPressed: _step == 1 && _sportsPicked.isEmpty
                          ? null
                          : _next,
                    ),
                  ),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: TextAction(
                label: _step == _totalSteps
                    ? 'Skip — finish setup'
                    : 'Skip for now',
                color: AppColors.muted,
                onPressed: _busy
                    ? null
                    : () => _step == _totalSteps
                          ? _finish()
                          : setState(() => _step++),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _sportsStep() => Wrap(
    spacing: 12,
    runSpacing: 12,
    children: [
      for (final (name, emoji) in _sports)
        _Tile(
          emoji: emoji,
          label: name,
          selected: _sportsPicked.contains(name),
          onTap: () => setState(
            () => _sportsPicked.contains(name)
                ? _sportsPicked.remove(name)
                : _sportsPicked.add(name),
          ),
        ),
    ],
  );

  Widget _tagsStep() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _TagField(
        label: 'FAVOURITE TEAMS',
        hint: 'Lakers, Chiefs, Real Madrid…',
        controller: _teamInput,
        tags: _teams,
        onAdd: () => _addTag(_teamInput, _teams),
        onRemove: (tag) => setState(() => _teams.remove(tag)),
      ),
      const SizedBox(height: 24),
      _TagField(
        label: 'FAVOURITE PLAYERS',
        hint: 'LeBron, Mahomes, Messi…',
        controller: _playerInput,
        tags: _players,
        onAdd: () => _addTag(_playerInput, _players),
        onRemove: (tag) => setState(() => _players.remove(tag)),
      ),
    ],
  );

  Widget _roleStep() => Column(
    children: [
      for (final (name, emoji) in _roles)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: AppPanel(
            onTap: () => setState(() => _role = name),
            borderColor: _role == name ? AppColors.cyan : AppColors.border,
            color: _role == name ? AppColors.chipOn : AppColors.panel,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            child: Row(
              children: [
                Text(emoji, style: const TextStyle(fontSize: 22)),
                const SizedBox(width: 14),
                Expanded(
                  child: Text(
                    name,
                    style: TextStyle(
                      fontSize: 15.5,
                      fontWeight: FontWeight.w600,
                      color: _role == name ? AppColors.text : AppColors.muted,
                    ),
                  ),
                ),
                if (_role == name)
                  const Icon(
                    Icons.check_circle_rounded,
                    color: AppColors.cyan,
                    size: 20,
                  ),
              ],
            ),
          ),
        ),
    ],
  );
}

class _Tile extends StatelessWidget {
  const _Tile({
    required this.emoji,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String emoji;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    // Two per row on any phone width, with the gutter and spacing removed.
    final width = (MediaQuery.sizeOf(context).width - 40 - 12) / 2;
    return SizedBox(
      width: width,
      child: AppPanel(
        onTap: onTap,
        color: selected ? AppColors.chipOn : AppColors.panel,
        borderColor: selected ? AppColors.cyan : AppColors.border,
        padding: const EdgeInsets.symmetric(vertical: 20),
        child: Column(
          children: [
            Text(emoji, style: const TextStyle(fontSize: 28)),
            const SizedBox(height: 8),
            Text(
              label,
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: FontWeight.w700,
                color: selected ? AppColors.cyan : AppColors.text,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TagField extends StatelessWidget {
  const _TagField({
    required this.label,
    required this.hint,
    required this.controller,
    required this.tags,
    required this.onAdd,
    required this.onRemove,
  });

  final String label;
  final String hint;
  final TextEditingController controller;
  final List<String> tags;
  final VoidCallback onAdd;
  final void Function(String) onRemove;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SectionLabel(label),
      const SizedBox(height: 10),
      TextField(
        controller: controller,
        textInputAction: TextInputAction.done,
        textCapitalization: TextCapitalization.words,
        onSubmitted: (_) => onAdd(),
        decoration: InputDecoration(
          hintText: hint,
          suffixIcon: IconButton(
            icon: const Icon(Icons.add_rounded, color: AppColors.cyan),
            onPressed: onAdd,
          ),
        ),
      ),
      if (tags.isNotEmpty) ...[
        const SizedBox(height: 12),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final tag in tags)
              Chip(
                label: Text(
                  tag,
                  style: const TextStyle(fontSize: 13, color: AppColors.text),
                ),
                backgroundColor: AppColors.chipOff,
                side: const BorderSide(color: AppColors.border),
                deleteIcon: const Icon(
                  Icons.close_rounded,
                  size: 16,
                  color: AppColors.muted,
                ),
                onDeleted: () => onRemove(tag),
              ),
          ],
        ),
      ],
    ],
  );
}

/// The last step reuses the same connect widget the Account screen uses, so
/// there is exactly one Instagram flow in the app.
class _InstagramStep extends StatelessWidget {
  const _InstagramStep();

  @override
  Widget build(BuildContext context) => const Column(
    children: [
      InstagramConnectCard(),
      SizedBox(height: 16),
      Notice(
        text:
            'Clips publish as Reels, one at a time, and only when you '
            'explicitly tap Publish. Nothing is posted automatically.',
        icon: Icons.lock_outline_rounded,
      ),
    ],
  );
}
