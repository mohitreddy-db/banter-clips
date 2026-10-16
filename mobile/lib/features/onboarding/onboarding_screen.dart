import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../api/errors.dart';
import '../../models/catalog.dart' as catalog;
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';
import '../account/instagram_connect.dart';
import '../account/purchases.dart';
import '../account/upgrade_sheet.dart';

/// Onboarding — the port of `frontend/src/pages/Onboarding.jsx`.
///
/// Five steps: sports, favourite teams and players, what kind of creator you
/// are, connecting your accounts, and picking a plan. Steps 2–5 are
/// skippable. Each step saves as it is completed (so nothing is lost if the
/// app is killed, or if a consent screen takes the user out to the browser
/// and back); the `onboarding_completed` flag is only set at the very end.
///
/// The plan step sells through the store, not Stripe (Apple 3.1.1 / Google
/// Play policy): "Go Creator" opens the same paywall every locked control
/// opens, and the server decides the plan after verifying the receipt.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  static const _totalSteps = 5;

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

  void _skip() {
    ref.read(apiClientProvider).track('onboarding_step_skipped', {
      'step': _step,
    });
    _next();
  }

  /// "Go Creator" on the last step: open the paywall, and once the server
  /// has confirmed the plan, finish setup as normal.
  Future<void> _goCreator() async {
    await showUpgradeSheet(context, reason: UpgradeReason.limit);
    if (!mounted) return;
    if (ref.read(appStateProvider).isCreator) {
      ref.read(purchaseControllerProvider.notifier).reset();
      await _finish();
    }
  }

  void _addTag(TextEditingController controller, List<String> into) {
    final value = controller.text.trim();
    controller.clear();
    if (value.isEmpty || into.contains(value)) return;
    setState(() => into.add(value));
  }

  @override
  Widget build(BuildContext context) {
    const titles = {
      1: 'What sports are you into?',
      2: 'Favorite teams & players',
      3: 'How will you use BanterClips?',
      4: 'Connect your accounts',
      5: 'Pick your plan',
    };
    const subtitles = {
      1: "Pick as many as you like — we'll pre-select your Studio and tailor example takes.",
      2: "Optional — helps us suggest take ideas you'll actually want to post.",
      3: 'It shapes the tone we suggest.',
      4: 'Publish everywhere in one click. You can always do this later.',
      5: 'Start free and publish today — or unlock downloads from day one. Change anytime.',
    };
    final optional = _step >= 4;
    final isCreator = ref.watch(appStateProvider).isCreator;

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
                  4 => const _AccountsStep(),
                  _ => _planStep(isCreator),
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
                      label: '← Back',
                      expand: false,
                      onPressed: _busy ? null : () => setState(() => _step--),
                    ),
                  if (_step > 1) const SizedBox(width: 10),
                  Expanded(
                    child: _step == _totalSteps
                        ? GradButton(
                            label: isCreator
                                ? "I'm ready"
                                : 'Start free & finish setup',
                            loading: _busy,
                            onPressed: _busy ? null : _next,
                          )
                        : GradButton(
                            label: 'Continue →',
                            loading: _busy,
                            onPressed: _step == 1 && _sportsPicked.isEmpty
                                ? null
                                : _next,
                          ),
                  ),
                ],
              ),
            ),
            if (_step > 1 && _step < _totalSteps)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: TextAction(
                  label: 'Skip for now',
                  color: AppColors.muted,
                  onPressed: _busy ? null : _skip,
                ),
              )
            else
              const SizedBox(height: 8),
          ],
        ),
      ),
    );
  }

  Widget _sportsStep() => GridView.count(
    crossAxisCount: 3,
    shrinkWrap: true,
    physics: const NeverScrollableScrollPhysics(),
    mainAxisSpacing: 10,
    crossAxisSpacing: 10,
    childAspectRatio: 1.15,
    children: [
      for (final sport in catalog.sports)
        _Tile(
          emoji: sport.emoji,
          label: sport.key,
          selected: _sportsPicked.contains(sport.key),
          onTap: () => setState(
            () => _sportsPicked.contains(sport.key)
                ? _sportsPicked.remove(sport.key)
                : _sportsPicked.add(sport.key),
          ),
        ),
    ],
  );

  Widget _tagsStep() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _TagField(
        label: 'FAVORITE TEAMS',
        hint: 'Lakers, Chiefs, Real Madrid…',
        controller: _teamInput,
        tags: _teams,
        suggestions: catalog
            .subjectSuggestions(_sportsPicked, players: false, limit: 10)
            .where((s) => !_teams.contains(s))
            .toList(),
        onAdd: () => _addTag(_teamInput, _teams),
        onPick: (tag) => setState(() => _teams.add(tag)),
        onRemove: (tag) => setState(() => _teams.remove(tag)),
      ),
      const SizedBox(height: 24),
      _TagField(
        label: 'FAVORITE PLAYERS',
        hint: 'LeBron, Mahomes, Messi…',
        controller: _playerInput,
        tags: _players,
        suggestions: catalog
            .subjectSuggestions(_sportsPicked, players: true, limit: 10)
            .where((s) => !_players.contains(s))
            .toList(),
        onAdd: () => _addTag(_playerInput, _players),
        onPick: (tag) => setState(() => _players.add(tag)),
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

  Widget _planStep(bool isCreator) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      _PlanCard(
        name: 'Free',
        price: r'$0',
        features: const [
          'Welcome credits — your first video on us',
          'One-click publish to Instagram, TikTok & YouTube',
          'All five tones, Funny to Roast',
          'Watermark on every clip',
        ],
        cta: isCreator ? 'Included in Creator' : 'Start free',
        current: !isCreator,
        onTap: isCreator ? null : _next,
      ),
      const SizedBox(height: 14),
      _PlanCard(
        name: 'Creator',
        price: r'$19',
        popular: true,
        features: const [
          '150 credits every month',
          'Full HD 1080p quality',
          '30-second videos',
          '500-character prompts',
          'Download in HD — no watermark',
          'Publish without the watermark',
          'Priority render queue',
        ],
        cta: isCreator ? '✓ Your plan' : 'Go Creator',
        current: isCreator,
        onTap: isCreator ? null : _goCreator,
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
  Widget build(BuildContext context) => AppPanel(
    onTap: onTap,
    color: selected ? AppColors.chipOn : AppColors.panel,
    borderColor: selected ? AppColors.cyan : AppColors.border,
    padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 6),
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(emoji, style: const TextStyle(fontSize: 26)),
        const SizedBox(height: 6),
        Text(
          label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            fontSize: 13,
            fontWeight: FontWeight.w700,
            color: selected ? AppColors.cyan : AppColors.text,
          ),
        ),
      ],
    ),
  );
}

class _TagField extends StatelessWidget {
  const _TagField({
    required this.label,
    required this.hint,
    required this.controller,
    required this.tags,
    required this.suggestions,
    required this.onAdd,
    required this.onPick,
    required this.onRemove,
  });

  final String label;
  final String hint;
  final TextEditingController controller;
  final List<String> tags;
  final List<String> suggestions;
  final VoidCallback onAdd;
  final void Function(String) onPick;
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
          prefixIcon: const Icon(Icons.search_rounded, color: AppColors.muted2),
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
                backgroundColor: AppColors.chipOn,
                side: BorderSide(color: AppColors.cyan.withValues(alpha: 0.5)),
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
      if (suggestions.isNotEmpty) ...[
        const SizedBox(height: 10),
        Wrap(
          spacing: 7,
          runSpacing: 7,
          children: [
            for (final suggestion in suggestions)
              AppChip(
                label: '+ $suggestion',
                dashed: true,
                onTap: () => onPick(suggestion),
              ),
          ],
        ),
      ],
    ],
  );
}

/// Step 4 reuses the same connect widgets the Account screen uses, so there
/// is exactly one connect flow per platform in the app.
class _AccountsStep extends StatelessWidget {
  const _AccountsStep();

  @override
  Widget build(BuildContext context) => Column(
    children: [
      const InstagramConnectCard(),
      const SizedBox(height: 10),
      const SocialConnectCard(platform: 'tiktok'),
      const SizedBox(height: 10),
      const SocialConnectCard(platform: 'youtube'),
      const SizedBox(height: 10),
      AppCard(
        child: Row(
          children: [
            Container(
              width: 40,
              height: 40,
              decoration: BoxDecoration(
                color: AppColors.panel,
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: AppColors.border),
              ),
              child: const Icon(
                Icons.alternate_email_rounded,
                color: AppColors.text,
                size: 21,
              ),
            ),
            const SizedBox(width: 14),
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('X', style: TextStyle(fontWeight: FontWeight.w700)),
                  SizedBox(height: 3),
                  Text(
                    'Video post with caption',
                    style: TextStyle(fontSize: 12, color: AppColors.muted),
                  ),
                ],
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
              decoration: BoxDecoration(
                color: AppColors.chipOff,
                borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                border: Border.all(color: AppColors.border),
              ),
              child: const Text(
                'Coming soon',
                style: TextStyle(fontSize: 11, color: AppColors.muted),
              ),
            ),
          ],
        ),
      ),
      const SizedBox(height: 16),
      const Notice(
        text:
            'Clips publish one at a time, and only when you explicitly tap '
            'Publish. Nothing is posted automatically.',
        icon: Icons.lock_outline_rounded,
      ),
    ],
  );
}

class _PlanCard extends StatelessWidget {
  const _PlanCard({
    required this.name,
    required this.price,
    required this.features,
    required this.cta,
    required this.current,
    required this.onTap,
    this.popular = false,
  });

  final String name;
  final String price;
  final List<String> features;
  final String cta;
  final bool current;
  final bool popular;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) => AppCard(
    borderColor: current
        ? AppColors.green
        : popular
        ? AppColors.cyan
        : AppColors.border,
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (current || popular)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Text(
              current ? 'YOUR PLAN' : 'MOST POPULAR',
              style: TextStyle(
                fontSize: 10.5,
                fontWeight: FontWeight.w800,
                letterSpacing: 1.2,
                color: current ? AppColors.green : AppColors.cyan,
              ),
            ),
          ),
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              name,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: AppColors.text,
              ),
            ),
            const Spacer(),
            Text(
              price,
              style: const TextStyle(
                fontSize: 28,
                fontWeight: FontWeight.w800,
                color: AppColors.text,
              ),
            ),
            const Padding(
              padding: EdgeInsets.only(bottom: 5, left: 3),
              child: Text(
                '/mo',
                style: TextStyle(fontSize: 13, color: AppColors.muted),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        for (final feature in features)
          Padding(
            padding: const EdgeInsets.only(bottom: 7),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  '✓',
                  style: TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppColors.green,
                  ),
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    feature,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w500,
                      color: AppColors.text,
                    ),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: 8),
        if (popular && !current)
          GradButton(label: cta, height: 46, onPressed: onTap)
        else
          GhostButton(
            label: cta,
            height: 46,
            color: current ? AppColors.green : AppColors.text,
            onPressed: onTap,
          ),
      ],
    ),
  );
}
