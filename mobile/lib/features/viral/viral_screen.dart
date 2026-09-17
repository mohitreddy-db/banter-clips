import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/catalog.dart' as catalog;
import '../../models/social.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../studio/trending_section.dart';

/// Viral — the port of `frontend/src/pages/Viral.jsx`.
///
/// What fans are arguing about in the last 48 hours, per sport, with a
/// one-tap preset for each angle. Tapping one opens the create screen with
/// the take, tone, length and sport filled in — the real flow, not a
/// shortcut around it: the user still reviews the script before anything
/// is spent.
class ViralScreen extends ConsumerStatefulWidget {
  const ViralScreen({super.key});

  @override
  ConsumerState<ViralScreen> createState() => _ViralScreenState();
}

class _ViralScreenState extends ConsumerState<ViralScreen> {
  String? _sport;
  bool _refreshing = false;
  Timer? _tick;

  @override
  void initState() {
    super.initState();
    // Re-render every second while a refresh cooldown is counting down.
    _tick = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  /// The user's sports first, then everything else — as on the web.
  List<String> _ordered(List<String> followed) {
    final mine = followed.where(catalog.isKnownSport).toList();
    return [...mine, ...catalog.sportKeys.where((s) => !mine.contains(s))];
  }

  Future<void> _refresh(String sport) async {
    setState(() => _refreshing = true);
    ref.read(apiClientProvider).track('viral_refreshed', {'sport': sport});
    try {
      final fresh = await ref.read(apiClientProvider).trending(sport, refresh: true);
      trendingCache.put(sport, fresh);
      ref.invalidate(trendingProvider(sport));
    } catch (_) {
      // The old feed stays on screen; nothing to say.
    } finally {
      if (mounted) setState(() => _refreshing = false);
    }
  }

  void _use(String sport, TrendingPrompt prompt, String kind) {
    ref.read(apiClientProvider).track('viral_preset_used', {
      'sport': sport,
      'kind': kind,
      'tone': prompt.tone,
      'seconds': prompt.seconds,
    });
    final query = Uri(
      queryParameters: {
        'prompt': prompt.take,
        'tone': prompt.tone,
        'seconds': '${prompt.seconds}',
        'sport': sport,
      },
    ).query;
    context.go('/studio?$query');
  }

  @override
  Widget build(BuildContext context) {
    final followed =
        ref.watch(appStateProvider).user?.preferences.sports ?? const [];
    final order = _ordered(followed);
    final sport = _sport ?? order.first;
    final feed = ref.watch(trendingProvider(sport));

    return Scaffold(
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          children: [
            Text(
              "🔥 What's viral right now",
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            const Text(
              'Real stories from the last 48 hours. Tap an angle — the take is '
              'written for you, you approve the script, we make the video.',
              style: TextStyle(
                fontSize: 13.5,
                height: 1.5,
                color: AppColors.muted,
              ),
            ),
            const SizedBox(height: 16),
            SizedBox(
              height: 42,
              child: ListView.separated(
                scrollDirection: Axis.horizontal,
                itemCount: order.length,
                separatorBuilder: (_, __) => const SizedBox(width: 8),
                itemBuilder: (context, i) => AppChip(
                  label: '${catalog.sportEmoji(order[i])} ${order[i]}',
                  selected: order[i] == sport,
                  onTap: () => setState(() => _sport = order[i]),
                ),
              ),
            ),
            const SizedBox(height: 18),
            SectionLabel(
              '🔥 TRENDING NOW · ${sport.toUpperCase()}',
              trailing: feed.maybeWhen(
                data: (data) => _RefreshButton(
                  data: data,
                  refreshing: _refreshing,
                  onRefresh: () => _refresh(sport),
                ),
                orElse: () => null,
              ),
            ),
            const SizedBox(height: 10),
            feed.when(
              loading: () => const Column(
                children: [
                  _ScanningLine(),
                  SizedBox(height: 10),
                  Skeleton(height: 150),
                  SizedBox(height: 10),
                  Skeleton(height: 150),
                  SizedBox(height: 10),
                  Skeleton(height: 150),
                ],
              ),
              error: (_, __) => _Empty(sport: sport, failed: true),
              data: (data) => data.isEmpty
                  ? _Empty(sport: sport, failed: false)
                  : Column(
                      children: [
                        for (final topic in data.topics)
                          Padding(
                            padding: const EdgeInsets.only(bottom: 10),
                            child: _TopicCard(
                              topic: topic,
                              onUse: (prompt, kind) =>
                                  _use(sport, prompt, kind),
                            ),
                          ),
                      ],
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

class _RefreshButton extends StatelessWidget {
  const _RefreshButton({
    required this.data,
    required this.refreshing,
    required this.onRefresh,
  });

  final TrendingFeed data;
  final bool refreshing;
  final VoidCallback onRefresh;

  @override
  Widget build(BuildContext context) {
    final wait = data.secondsUntilRefresh;
    final locked = wait > 0 || refreshing;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        if (data.fetchedAt != null)
          Text(
            _ago(data.fetchedAt!),
            style: const TextStyle(fontSize: 11, color: AppColors.muted2),
          ),
        const SizedBox(width: 8),
        Material(
          color: AppColors.surface,
          borderRadius: BorderRadius.circular(AppTheme.radiusPill),
          child: InkWell(
            onTap: locked ? null : onRefresh,
            borderRadius: BorderRadius.circular(AppTheme.radiusPill),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                border: Border.all(
                  color: locked
                      ? AppColors.border
                      : AppColors.cyan.withValues(alpha: 0.45),
                ),
              ),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (refreshing)
                    const InlineSpinner(size: 11)
                  else
                    Icon(
                      Icons.refresh_rounded,
                      size: 13,
                      color: locked ? AppColors.muted2 : AppColors.cyan,
                    ),
                  const SizedBox(width: 5),
                  Text(
                    refreshing
                        ? 'Refreshing…'
                        : wait > 0
                        ? 'Fresh · ${wait}s'
                        : 'Refresh',
                    style: TextStyle(
                      fontSize: 11.5,
                      fontWeight: FontWeight.w700,
                      color: locked ? AppColors.muted2 : AppColors.cyan,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  static String _ago(DateTime at) {
    final minutes = DateTime.now().difference(at).inMinutes;
    return minutes < 1 ? 'updated just now' : 'updated ${minutes}m ago';
  }
}

/// The rotating "Scanning today's internet…" line shown while the first
/// feed for a sport is built.
class _ScanningLine extends StatefulWidget {
  const _ScanningLine();

  @override
  State<_ScanningLine> createState() => _ScanningLineState();
}

class _ScanningLineState extends State<_ScanningLine> {
  static const _lines = [
    "Scanning today's internet…",
    'Reading fan chatter on socials…',
    "Ranking what's blowing up…",
    'Writing angles you can shoot…',
  ];
  int _i = 0;
  Timer? _timer;

  @override
  void initState() {
    super.initState();
    _timer = Timer.periodic(const Duration(milliseconds: 1700), (_) {
      if (mounted) setState(() => _i = (_i + 1) % _lines.length);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Row(
    children: [
      const InlineSpinner(size: 9),
      const SizedBox(width: 9),
      AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        child: Text(
          _lines[_i],
          key: ValueKey(_i),
          style: const TextStyle(fontSize: 12.5, color: AppColors.muted),
        ),
      ),
    ],
  );
}

class _Empty extends StatelessWidget {
  const _Empty({required this.sport, required this.failed});

  final String sport;
  final bool failed;

  @override
  Widget build(BuildContext context) => AppCard(
    child: Column(
      children: [
        const Text('📡', style: TextStyle(fontSize: 30)),
        const SizedBox(height: 8),
        Text(
          failed
              ? "Couldn't reach the internet just now"
              : 'Nothing viral in $sport yet',
          textAlign: TextAlign.center,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: AppColors.text,
          ),
        ),
        const SizedBox(height: 6),
        const Text(
          'Try another sport above, or write your own take — the Studio '
          'still writes the script for you.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 13, height: 1.5, color: AppColors.muted),
        ),
        const SizedBox(height: 14),
        GhostButton(
          label: 'Write my own take →',
          expand: false,
          height: 42,
          fontSize: 13.5,
          onPressed: () => context.go('/studio'),
        ),
      ],
    ),
  );
}

class _TopicCard extends StatefulWidget {
  const _TopicCard({required this.topic, required this.onUse});

  final TrendingTopic topic;
  final void Function(TrendingPrompt prompt, String kind) onUse;

  @override
  State<_TopicCard> createState() => _TopicCardState();
}

class _TopicCardState extends State<_TopicCard> {
  bool _showPrompts = false;

  static const _heat = {
    'viral': ('🔥', 'VIRAL', Color(0xFFF97316)),
    'hot': ('⚡', 'HOT', AppColors.cyan),
    'rising': ('📈', 'RISING', AppColors.green),
  };

  @override
  Widget build(BuildContext context) {
    final topic = widget.topic;
    final (emoji, label, color) = _heat[topic.heat] ?? _heat['hot']!;

    return AppCard(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                margin: const EdgeInsets.only(top: 2),
                padding: const EdgeInsets.symmetric(
                  horizontal: 8,
                  vertical: 3,
                ),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                  border: Border.all(color: color),
                ),
                child: Text(
                  '$emoji $label',
                  style: TextStyle(
                    fontSize: 9.5,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.5,
                    color: color,
                  ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      topic.title,
                      style: const TextStyle(
                        fontSize: 16.5,
                        fontWeight: FontWeight.w800,
                        height: 1.25,
                        color: AppColors.text,
                      ),
                    ),
                    if (topic.whyNow.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        topic.whyNow,
                        style: const TextStyle(
                          fontSize: 12.5,
                          height: 1.45,
                          color: AppColors.muted,
                        ),
                      ),
                    ],
                    if (topic.summary.isNotEmpty) ...[
                      const SizedBox(height: 4),
                      Text(
                        topic.summary,
                        style: const TextStyle(
                          fontSize: 12.5,
                          height: 1.45,
                          color: AppColors.muted2,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ],
          ),
          if (topic.presets.isNotEmpty) ...[
            const SizedBox(height: 14),
            const Text(
              'CREATE · ONE TAP',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                letterSpacing: 1,
                color: AppColors.muted2,
              ),
            ),
            const SizedBox(height: 8),
            GridView.count(
              crossAxisCount: 2,
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 2.6,
              children: [
                for (final preset in topic.presets)
                  AppPanel(
                    onTap: () => widget.onUse(preset, preset.key),
                    color: AppColors.cyanWash(0.06),
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 8,
                    ),
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${preset.icon} ${preset.label}'.trim(),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            fontSize: 13.5,
                            fontWeight: FontWeight.w700,
                            color: AppColors.text,
                          ),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          '${preset.tone} · ${preset.seconds}s',
                          style: const TextStyle(
                            fontSize: 11,
                            color: AppColors.muted2,
                          ),
                        ),
                      ],
                    ),
                  ),
              ],
            ),
          ],
          if (topic.prompts.isNotEmpty) ...[
            const SizedBox(height: 12),
            InkWell(
              onTap: () => setState(() => _showPrompts = !_showPrompts),
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 4),
                child: Text(
                  '✨ Or use a ready-written take ${_showPrompts ? '▴' : '▾'}',
                  style: const TextStyle(
                    fontSize: 12.5,
                    fontWeight: FontWeight.w700,
                    color: AppColors.cyan,
                  ),
                ),
              ),
            ),
            if (_showPrompts) ...[
              const SizedBox(height: 6),
              for (final prompt in topic.prompts)
                Padding(
                  padding: const EdgeInsets.only(bottom: 8),
                  child: AppPanel(
                    onTap: () => widget.onUse(prompt, 'ready'),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text.rich(
                          TextSpan(
                            children: [
                              TextSpan(
                                text: (prompt.angle.isEmpty
                                        ? 'Take this angle'
                                        : prompt.angle)
                                    .toUpperCase(),
                                style: const TextStyle(
                                  fontSize: 10.5,
                                  fontWeight: FontWeight.w700,
                                  letterSpacing: 0.6,
                                  color: AppColors.cyan,
                                ),
                              ),
                              TextSpan(
                                text: ' · ${prompt.tone} · ${prompt.seconds}s',
                                style: const TextStyle(
                                  fontSize: 10.5,
                                  color: AppColors.muted2,
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 5),
                        Text(
                          '“${prompt.take}”',
                          style: const TextStyle(
                            fontSize: 13.5,
                            height: 1.45,
                            fontWeight: FontWeight.w500,
                            color: AppColors.text,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          ],
        ],
      ),
    );
  }
}
