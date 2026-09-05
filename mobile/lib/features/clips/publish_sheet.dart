import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/errors.dart';
import '../../models/clip.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../account/instagram_connect.dart';

/// Publish to Instagram — the port of `PublishModal` in
/// `frontend/src/components/Modals.jsx`.
///
/// Fire-and-forget by design: the upload runs server-side and the clips
/// library shows live status, so the user is never trapped watching a
/// progress bar they cannot influence.
Future<void> showPublishSheet(BuildContext context, Clip clip) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (context) => Padding(
        // Lift the sheet above the keyboard — the caption box is the point
        // of this sheet, and a covered text field is a dead end.
        padding: EdgeInsets.only(
          bottom: MediaQuery.viewInsetsOf(context).bottom,
        ),
        child: _PublishSheet(clip: clip),
      ),
    );

class _PublishSheet extends ConsumerStatefulWidget {
  const _PublishSheet({required this.clip});

  final Clip clip;

  @override
  ConsumerState<_PublishSheet> createState() => _PublishSheetState();
}

class _PublishSheetState extends ConsumerState<_PublishSheet> {
  late final TextEditingController _caption = TextEditingController(
    text: '${widget.clip.take} 😤 #${widget.clip.sport} #HotTake #BanterClips',
  );

  List<String> _suggestions = const [];

  /// Everything shown so far, sent back on regenerate so new options are
  /// genuinely new rather than a reshuffle of the same three.
  final List<String> _seen = [];
  bool _loadingSuggestions = true;
  bool _publishing = false;
  bool _queued = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _fetchSuggestions();
  }

  @override
  void dispose() {
    _caption.dispose();
    super.dispose();
  }

  Future<void> _fetchSuggestions({bool regenerate = false}) async {
    setState(() => _loadingSuggestions = true);
    try {
      final captions = await ref
          .read(apiClientProvider)
          .captionSuggestions(
            widget.clip.id,
            avoid: regenerate ? _seen : const [],
          );
      if (!mounted || captions.isEmpty) return;
      setState(() {
        _seen.addAll(captions);
        _suggestions = captions;
        // Follow along unless the user has typed their own caption.
        if (!regenerate ||
            _seen.contains(_caption.text) ||
            _caption.text.isEmpty) {
          _caption.text = captions.first;
        }
      });
    } on ApiException {
      // Suggestions are a nicety — the box still works without them.
    } finally {
      if (mounted) setState(() => _loadingSuggestions = false);
    }
  }

  Future<void> _publish() async {
    final account = ref.read(appStateProvider).instagram;
    if (account == null) return;
    setState(() {
      _publishing = true;
      _error = '';
    });
    try {
      await ref
          .read(apiClientProvider)
          .publishClip(
            clipId: widget.clip.id,
            socialAccountId: account.id,
            caption: _caption.text,
          );
      unawaited(ref.read(appStateProvider.notifier).refreshClips());
      if (mounted) setState(() => _queued = true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _publishing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appStateProvider);
    final connected = state.instagramConnected;

    if (_queued)
      return _QueuedConfirmation(watermarked: widget.clip.watermarked);

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Publish to Instagram',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 16),

            if (!connected) ...[
              const InstagramConnectCard(),
              const SizedBox(height: 16),
            ] else
              AppPanel(
                child: Row(
                  children: [
                    Container(
                      width: 30,
                      height: 30,
                      decoration: const BoxDecoration(
                        gradient: AppColors.instagram,
                        shape: BoxShape.circle,
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Instagram · ${state.instagram!.handle}',
                            style: Theme.of(context).textTheme.titleSmall,
                          ),
                          const SizedBox(height: 2),
                          const Text(
                            '● Connected — publishes as a Reel',
                            style: TextStyle(
                              fontSize: 11.5,
                              color: AppColors.green,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),

            const SizedBox(height: 18),
            const SectionLabel('CAPTION'),
            const SizedBox(height: 8),
            TextField(
              controller: _caption,
              maxLines: 4,
              minLines: 3,
              maxLength: 2200,
              textCapitalization: TextCapitalization.sentences,
              style: const TextStyle(
                fontSize: 15,
                height: 1.45,
                color: AppColors.text,
              ),
              decoration: const InputDecoration(counterText: ''),
            ),

            if (_loadingSuggestions || _suggestions.isNotEmpty) ...[
              const SizedBox(height: 14),
              SectionLabel(
                _loadingSuggestions ? 'WRITING SUGGESTIONS…' : 'OR PICK ONE',
                trailing: _loadingSuggestions
                    ? null
                    : TextAction(
                        label: '↻ New suggestions',
                        fontSize: 12,
                        onPressed: () => _fetchSuggestions(regenerate: true),
                      ),
              ),
              const SizedBox(height: 8),
              if (_loadingSuggestions) ...[
                const Skeleton(height: 44),
                const SizedBox(height: 7),
                const Skeleton(height: 44),
              ] else
                for (final suggestion in _suggestions)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 7),
                    child: AppPanel(
                      onTap: () => setState(() => _caption.text = suggestion),
                      color: _caption.text == suggestion
                          ? AppColors.cyanWash(0.10)
                          : Colors.transparent,
                      borderColor: _caption.text == suggestion
                          ? AppColors.cyan
                          : AppColors.border,
                      child: Text(
                        suggestion,
                        style: TextStyle(
                          fontSize: 13,
                          height: 1.45,
                          color: _caption.text == suggestion
                              ? AppColors.text
                              : AppColors.muted,
                        ),
                      ),
                    ),
                  ),
            ],

            if (widget.clip.watermarked) ...[
              const SizedBox(height: 14),
              const Notice(
                text:
                    'Free plan: your Reel publishes with the BanterClips watermark. '
                    'Creator publishes clean.',
                icon: Icons.info_outline_rounded,
              ),
            ],
            if (_error.isNotEmpty) ...[
              const SizedBox(height: 12),
              Notice.error(_error),
            ],

            const SizedBox(height: 18),
            GradButton(
              label: connected ? 'Publish now' : 'Connect Instagram first',
              loading: _publishing,
              onPressed: connected ? _publish : null,
            ),
          ],
        ),
      ),
    );
  }
}

class _QueuedConfirmation extends StatelessWidget {
  const _QueuedConfirmation({required this.watermarked});

  final bool watermarked;

  @override
  Widget build(BuildContext context) => SafeArea(
    child: Padding(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 58,
            height: 58,
            decoration: BoxDecoration(
              color: AppColors.cyanWash(0.12),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Center(
              child: Text('🚀', style: TextStyle(fontSize: 26)),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Publishing in the background',
            style: Theme.of(context).textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 10),
          Text(
            'Your Reel is uploading to Instagram'
            '${watermarked ? ' (with watermark)' : ''}. '
            'Track live status in My Clips — you can keep creating meanwhile.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 22),
          GradButton(
            label: 'Done',
            onPressed: () => Navigator.of(context).pop(),
          ),
        ],
      ),
    ),
  );
}
