import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../api/errors.dart';
import '../../models/clip.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../account/upgrade_sheet.dart';
import 'publish_sheet.dart';

/// My Clips — the port of `frontend/src/pages/Clips.jsx`.
///
/// A list rather than the web's grid: a 9:16 thumbnail beside two lines of
/// take reads better on a phone than a wall of cards, and it puts the actions
/// where a thumb can reach them.
///
/// Polling here follows the same rule as the clip screen: only while
/// something is actually in flight, only while the app is in the foreground.
class ClipsScreen extends ConsumerStatefulWidget {
  const ClipsScreen({super.key});

  @override
  ConsumerState<ClipsScreen> createState() => _ClipsScreenState();
}

class _ClipsScreenState extends ConsumerState<ClipsScreen>
    with WidgetsBindingObserver {
  Timer? _poll;
  String _error = '';
  bool _foreground = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    // Always refetch on open: jobs may have started from the studio since
    // the shared state last loaded the list.
    Future.microtask(() => ref.read(appStateProvider.notifier).refreshClips());
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _poll?.cancel();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _foreground = state == AppLifecycleState.resumed;
    if (_foreground) {
      ref.read(appStateProvider.notifier).refreshClips();
    } else {
      _poll?.cancel();
      _poll = null;
    }
    _syncPolling();
  }

  /// Start or stop the poll to match what the list actually contains. Called
  /// on every build, so it reacts the moment the last render finishes.
  void _syncPolling() {
    final live = ref.read(appStateProvider).hasLiveWork;
    if (live && _foreground) {
      _poll ??= Timer.periodic(
        const Duration(seconds: 3),
        (_) => ref.read(appStateProvider.notifier).refreshClips(),
      );
    } else {
      _poll?.cancel();
      _poll = null;
    }
  }

  Future<void> _delete(Clip clip) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this clip?'),
        content: const Text(
          'The video file is deleted too, permanently. This cannot be undone.',
          style: TextStyle(color: AppColors.muted, height: 1.5),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Keep it'),
          ),
          TextButton(
            onPressed: () => Navigator.of(context).pop(true),
            style: TextButton.styleFrom(foregroundColor: AppColors.error),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(apiClientProvider).deleteClip(clip.id);
      ref.read(appStateProvider.notifier).removeClip(clip.id);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  Future<void> _retry(Clip clip) async {
    try {
      final updated = await ref.read(apiClientProvider).retryClip(clip.id);
      ref.read(appStateProvider.notifier).mergeClip(updated);
      _syncPolling();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appStateProvider);
    // Watching the state here is what keeps the poll honest across rebuilds.
    WidgetsBinding.instance.addPostFrameCallback((_) => _syncPolling());

    return Scaffold(
      appBar: AppBar(
        title: const Text('My clips'),
        actions: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Center(
              child: Text(
                '${state.left}/${state.limit} left',
                style: const TextStyle(fontSize: 12.5, color: AppColors.muted),
              ),
            ),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: () => ref.read(appStateProvider.notifier).refreshClips(),
        color: AppColors.cyan,
        backgroundColor: AppColors.surface,
        child: state.clips.isEmpty
            ? ListView(
                // A scrollable is required for pull-to-refresh to work on an
                // empty list — otherwise the gesture has nothing to attach to.
                physics: const AlwaysScrollableScrollPhysics(),
                children: [
                  SizedBox(height: MediaQuery.sizeOf(context).height * 0.12),
                  EmptyState(
                    icon: '🎬',
                    title: 'No clips yet',
                    message: 'Head to Create and drop your first hot take.',
                    action: GradButton(
                      label: 'Create a clip',
                      expand: false,
                      onPressed: () => context.go('/studio'),
                    ),
                  ),
                ],
              )
            : ListView.separated(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 28),
                itemCount: state.clips.length + (_error.isEmpty ? 0 : 1),
                separatorBuilder: (_, __) => const SizedBox(height: 12),
                itemBuilder: (context, index) {
                  if (_error.isNotEmpty && index == 0)
                    return Notice.error(_error);
                  final clip = state.clips[_error.isEmpty ? index : index - 1];
                  return ClipCard(
                    clip: clip,
                    canDownload: state.canDownload,
                    onOpen: () => context.push('/clip/${clip.id}'),
                    onPublish: () => showPublishSheet(context, clip),
                    onRetry: () => _retry(clip),
                    onDelete: () => _delete(clip),
                    onLockedDownload: () => showUpgradeSheet(
                      context,
                      reason: UpgradeReason.download,
                    ),
                  );
                },
              ),
      ),
    );
  }
}

/// One clip in the library: poster, take, status, and the actions available
/// in that state.
class ClipCard extends StatelessWidget {
  const ClipCard({
    super.key,
    required this.clip,
    required this.canDownload,
    required this.onOpen,
    required this.onPublish,
    required this.onRetry,
    required this.onDelete,
    required this.onLockedDownload,
  });

  final Clip clip;
  final bool canDownload;
  final VoidCallback onOpen;
  final VoidCallback onPublish;
  final VoidCallback onRetry;
  final VoidCallback onDelete;
  final VoidCallback onLockedDownload;

  @override
  Widget build(BuildContext context) => AppCard(
    onTap: onOpen,
    padding: const EdgeInsets.all(12),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _Poster(clip: clip),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 7,
                          vertical: 3,
                        ),
                        decoration: BoxDecoration(
                          color: AppColors.chipOff,
                          borderRadius: BorderRadius.circular(6),
                        ),
                        child: Text(
                          '${clip.sport} · ${clip.tone.toUpperCase()}',
                          style: const TextStyle(
                            fontSize: 9.5,
                            fontWeight: FontWeight.w700,
                            color: AppColors.muted,
                          ),
                        ),
                      ),
                      const Spacer(),
                      if (clip.hasFailed || clip.isReady)
                        IconButton(
                          icon: const Icon(
                            Icons.delete_outline_rounded,
                            size: 19,
                          ),
                          color: AppColors.muted2,
                          visualDensity: VisualDensity.compact,
                          tooltip: 'Delete',
                          onPressed: onDelete,
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(
                    clip.take,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.35,
                      fontWeight: FontWeight.w600,
                      color: AppColors.text,
                    ),
                  ),
                  const SizedBox(height: 8),
                  _StatusLine(clip: clip),
                ],
              ),
            ),
          ],
        ),
        if (clip.isReady) ...[
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: GradButton(
                  label: clip.isPublishing
                      ? 'Publishing…'
                      : clip.publishFailed
                      ? 'Retry publish'
                      : 'Publish',
                  height: 40,
                  fontSize: 13.5,
                  onPressed: clip.isPublishing || clip.isPreparing
                      ? null
                      : onPublish,
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: canDownload
                    ? GhostButton(
                        label: 'Share',
                        icon: Icons.ios_share_rounded,
                        height: 40,
                        fontSize: 13.5,
                        // Sharing needs the file, which the clip screen
                        // already knows how to fetch — send them there
                        // rather than duplicating the download here.
                        onPressed: onOpen,
                      )
                    : GhostButton(
                        label: 'Share',
                        icon: Icons.lock_outline_rounded,
                        height: 40,
                        fontSize: 13,
                        dashed: true,
                        color: AppColors.muted2,
                        trailing: const CreatorPill(),
                        onPressed: onLockedDownload,
                      ),
              ),
            ],
          ),
        ],
        if (clip.hasFailed) ...[
          const SizedBox(height: 12),
          GradButton(
            label: '↻  Retry free',
            height: 40,
            fontSize: 13.5,
            onPressed: onRetry,
          ),
        ],
      ],
    ),
  );
}

class _Poster extends StatelessWidget {
  const _Poster({required this.clip});

  final Clip clip;

  @override
  Widget build(BuildContext context) => ClipRRect(
    borderRadius: BorderRadius.circular(10),
    child: SizedBox(
      width: 66,
      height: 108,
      child: Stack(
        fit: StackFit.expand,
        children: [
          // The gradient is the fallback for clips made before poster
          // frames were stored — never a blank grey box.
          DecoratedBox(
            decoration: BoxDecoration(gradient: AppColors.thumbFor(clip.id)),
          ),
          if ((clip.posterUrl ?? '').isNotEmpty)
            CachedNetworkImage(
              imageUrl: clip.posterUrl!,
              fit: BoxFit.cover,
              fadeInDuration: const Duration(milliseconds: 180),
              errorWidget: (_, __, ___) => const SizedBox.shrink(),
            ),
          if (clip.inFlight)
            Container(
              color: Colors.black.withValues(alpha: 0.45),
              child: const Center(
                child: InlineSpinner(size: 20, color: Colors.white),
              ),
            )
          else if (clip.hasFailed)
            Container(
              color: Colors.black.withValues(alpha: 0.45),
              child: const Center(
                child: Text('⚠️', style: TextStyle(fontSize: 18)),
              ),
            )
          else if (clip.isReady && !clip.isPreparing)
            Center(
              child: Container(
                width: 30,
                height: 30,
                decoration: BoxDecoration(
                  color: Colors.black.withValues(alpha: 0.45),
                  shape: BoxShape.circle,
                ),
                child: const Icon(
                  Icons.play_arrow_rounded,
                  size: 20,
                  color: Colors.white,
                ),
              ),
            ),
        ],
      ),
    ),
  );
}

class _StatusLine extends StatelessWidget {
  const _StatusLine({required this.clip});

  final Clip clip;

  @override
  Widget build(BuildContext context) {
    if (clip.inFlight) {
      return Text(
        clip.currentStep ?? clip.statusLabel,
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: const TextStyle(fontSize: 12, color: AppColors.cyan),
      );
    }
    if (clip.awaitingScript) {
      return const Text(
        '📝 Script ready — tap to review',
        style: TextStyle(
          fontSize: 12,
          fontWeight: FontWeight.w600,
          color: AppColors.cyan,
        ),
      );
    }
    if (clip.hasFailed) {
      return const Text(
        'Failed · retry is free',
        style: TextStyle(fontSize: 12, color: AppColors.error),
      );
    }

    // Ready. Say where the publish got to.
    final published = clip.publishedPost;
    return Wrap(
      spacing: 6,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text(
          clip.isPreparing ? 'preparing…' : '${clip.displaySeconds}s',
          style: const TextStyle(fontSize: 12, color: AppColors.muted),
        ),
        if (clip.isPublishing)
          const Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              InlineSpinner(size: 10),
              SizedBox(width: 5),
              Text(
                'publishing to Instagram…',
                style: TextStyle(fontSize: 12, color: AppColors.cyan),
              ),
            ],
          )
        else if (published != null)
          (published.externalUrl ?? '').isEmpty
              ? const Text(
                  '· published',
                  style: TextStyle(fontSize: 12, color: AppColors.green),
                )
              : InkWell(
                  onTap: () => launchUrl(
                    Uri.parse(published.externalUrl!),
                    mode: LaunchMode.externalApplication,
                  ),
                  child: const Text(
                    '· published — view post ↗',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      color: AppColors.green,
                    ),
                  ),
                )
        else if (clip.publishFailed)
          const Text(
            "· publish failed — retry, it's free",
            style: TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.error,
            ),
          )
        else
          const Text(
            '· not published yet',
            style: TextStyle(fontSize: 12, color: AppColors.muted2),
          ),
      ],
    );
  }
}
