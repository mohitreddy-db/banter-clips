import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/social.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';

/// Today's stories for the selected sport, each expandable into
/// ready-to-shoot takes. Port of `frontend/src/components/Trending.jsx`.
///
/// The feed is served from a shared 20-minute server cache per sport, so
/// switching sports back and forth is cheap. An empty feed is a valid answer
/// — it means web research is off on the server — and the section hides
/// itself rather than showing an empty box.
final trendingProvider = FutureProvider.family.autoDispose<TrendingFeed, String>(
  (ref, sport) async {
    // Keep the result alive past a rebuild so flicking between sports does not
    // refetch what we just loaded.
    ref.keepAlive();
    return ref.watch(apiClientProvider).trending(sport);
  },
);

class TrendingSection extends ConsumerStatefulWidget {
  const TrendingSection({super.key, required this.sport, required this.onUse});

  final String sport;

  /// Fills the take box as though the user typed it — the real flow, not a
  /// shortcut around it.
  final void Function(TrendingPrompt prompt) onUse;

  @override
  ConsumerState<TrendingSection> createState() => _TrendingSectionState();
}

class _TrendingSectionState extends ConsumerState<TrendingSection> {
  int _open = -1;

  void _refresh() {
    ref.invalidate(trendingProvider(widget.sport));
  }

  @override
  void didUpdateWidget(TrendingSection oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.sport != widget.sport) _open = -1;
  }

  @override
  Widget build(BuildContext context) {
    final feed = ref.watch(trendingProvider(widget.sport));

    return feed.when(
      loading: () => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SectionLabel('TRENDING IN ${widget.sport.toUpperCase()}'),
          const SizedBox(height: 10),
          const Skeleton(height: 62),
          const SizedBox(height: 8),
          const Skeleton(height: 62),
        ],
      ),
      // A failed feed is not worth an error message: trending is a nicety,
      // and the take box above it works perfectly without it.
      error: (_, __) => const SizedBox.shrink(),
      data: (data) {
        if (data.isEmpty) return const SizedBox.shrink();
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SectionLabel(
              'TRENDING IN ${widget.sport.toUpperCase()}',
              trailing: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    _agoLabel(data.fetchedAt),
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppColors.muted2,
                    ),
                  ),
                  const SizedBox(width: 3),
                  IconButton(
                    onPressed: feed.isRefreshing ? null : _refresh,
                    tooltip: 'Refresh trends',
                    visualDensity: VisualDensity.compact,
                    constraints: const BoxConstraints(
                      minWidth: 32,
                      minHeight: 32,
                    ),
                    padding: const EdgeInsets.all(7),
                    icon: feed.isRefreshing
                        ? const SizedBox.square(
                            dimension: 15,
                            child: CircularProgressIndicator(
                              strokeWidth: 1.8,
                              color: AppColors.cyan,
                            ),
                          )
                        : const Icon(
                            Icons.refresh_rounded,
                            size: 18,
                            color: AppColors.muted,
                          ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
            for (var i = 0; i < data.topics.length; i++)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _TopicTile(
                  topic: data.topics[i],
                  expanded: _open == i,
                  onToggle: () => setState(() => _open = _open == i ? -1 : i),
                  onUse: widget.onUse,
                ),
              ),
          ],
        );
      },
    );
  }

  static String _agoLabel(DateTime? at) {
    if (at == null) return '';
    final minutes = DateTime.now().difference(at).inMinutes;
    if (minutes < 1) return 'updated just now';
    return 'updated ${minutes}m ago';
  }
}

class _TopicTile extends StatelessWidget {
  const _TopicTile({
    required this.topic,
    required this.expanded,
    required this.onToggle,
    required this.onUse,
  });

  final TrendingTopic topic;
  final bool expanded;
  final VoidCallback onToggle;
  final void Function(TrendingPrompt) onUse;

  static const _heat = {
    'viral': ('🔥', 'VIRAL', Color(0xFFF97316)),
    'hot': ('⚡', 'HOT', AppColors.cyan),
    'rising': ('📈', 'RISING', AppColors.green),
  };

  @override
  Widget build(BuildContext context) {
    final (emoji, label, color) = _heat[topic.heat] ?? _heat['hot']!;

    return AppPanel(
      onTap: onToggle,
      borderColor: expanded
          ? AppColors.cyan.withValues(alpha: 0.5)
          : AppColors.border,
      padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(emoji, style: const TextStyle(fontSize: 15)),
              const SizedBox(width: 9),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      topic.title,
                      style: const TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w700,
                        color: AppColors.text,
                        height: 1.35,
                      ),
                    ),
                    if (topic.whyNow.isNotEmpty) ...[
                      const SizedBox(height: 3),
                      Text(
                        topic.whyNow,
                        style: const TextStyle(
                          fontSize: 11.5,
                          color: AppColors.muted,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const SizedBox(width: 8),
              Column(
                crossAxisAlignment: CrossAxisAlignment.end,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 7,
                      vertical: 3,
                    ),
                    decoration: BoxDecoration(
                      color: color.withValues(alpha: 0.14),
                      borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                    ),
                    child: Text(
                      label,
                      style: TextStyle(
                        fontSize: 8.5,
                        fontWeight: FontWeight.w800,
                        letterSpacing: 0.4,
                        color: color,
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Icon(
                    expanded
                        ? Icons.expand_less_rounded
                        : Icons.expand_more_rounded,
                    size: 18,
                    color: AppColors.muted2,
                  ),
                ],
              ),
            ],
          ),
          if (expanded) ...[
            if (topic.summary.isNotEmpty) ...[
              const SizedBox(height: 10),
              Text(
                topic.summary,
                style: const TextStyle(
                  fontSize: 12.5,
                  height: 1.5,
                  color: AppColors.muted,
                ),
              ),
            ],
            const SizedBox(height: 12),
            for (final prompt in topic.prompts)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: _PromptTile(prompt: prompt, onUse: () => onUse(prompt)),
              ),
            if (topic.prompts.isEmpty)
              const Text(
                'No takes written for this one yet — tap a different story.',
                style: TextStyle(fontSize: 12, color: AppColors.muted2),
              ),
          ],
        ],
      ),
    );
  }
}

class _PromptTile extends StatelessWidget {
  const _PromptTile({required this.prompt, required this.onUse});

  final TrendingPrompt prompt;
  final VoidCallback onUse;

  @override
  Widget build(BuildContext context) => Material(
    color: AppColors.cyanWash(0.06),
    borderRadius: BorderRadius.circular(AppTheme.radiusChip),
    child: InkWell(
      onTap: onUse,
      borderRadius: BorderRadius.circular(AppTheme.radiusChip),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 11),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(AppTheme.radiusChip),
          border: Border.all(color: AppColors.cyan.withValues(alpha: 0.25)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              prompt.take,
              style: const TextStyle(
                fontSize: 13.5,
                height: 1.45,
                fontWeight: FontWeight.w600,
                color: AppColors.text,
              ),
            ),
            const SizedBox(height: 7),
            Row(
              children: [
                Text(
                  [
                    if (prompt.angle.isNotEmpty) prompt.angle,
                    prompt.tone,
                    '${prompt.seconds}s',
                  ].join(' · '),
                  style: const TextStyle(fontSize: 11, color: AppColors.muted2),
                ),
                const Spacer(),
                const Text(
                  'Use this →',
                  style: TextStyle(
                    fontSize: 11.5,
                    fontWeight: FontWeight.w700,
                    color: AppColors.cyan,
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    ),
  );
}
