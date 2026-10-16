import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../api/errors.dart';
import '../../models/clip.dart';
import '../../models/social.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../account/instagram_connect.dart';

/// Publish a clip — the port of `PublishModal` in
/// `frontend/src/components/Modals.jsx`, with the three platforms it carries.
///
/// Instagram wants a caption. TikTok wants what its Content Posting API
/// insists on before every post: who can view it, which interactions are
/// allowed, and a commercial-content disclosure — all of it read live from
/// `/socials/tiktok/creator-info`, because TikTok decides those per account.
/// YouTube wants a title, description and visibility, reviewed before the
/// upload (their API-services terms). Nothing is ever posted without the
/// explicit tap at the bottom (BR-13).
///
/// Fire-and-forget by design: the upload runs server-side and the clips
/// library shows live status, so the user is never trapped watching a
/// progress bar they cannot influence.
Future<void> showPublishSheet(
  BuildContext context,
  Clip clip, {
  String? initialPlatform,
}) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  backgroundColor: AppColors.surface,
  builder: (context) => Padding(
    // Lift the sheet above the keyboard — the caption box is the point of
    // this sheet, and a covered text field is a dead end.
    padding: EdgeInsets.only(bottom: MediaQuery.viewInsetsOf(context).bottom),
    child: _PublishSheet(clip: clip, initialPlatform: initialPlatform),
  ),
);

const _platforms = [
  ('instagram', 'Instagram', 'publishes as a Reel'),
  ('tiktok', 'TikTok', 'posts to your TikTok'),
  ('youtube', 'YouTube', 'uploads as a YouTube Short'),
];

String platformName(String key) {
  for (final (k, name, _) in _platforms) {
    if (k == key) return name;
  }
  return key;
}

const _tiktokPrivacyLabels = {
  'PUBLIC_TO_EVERYONE': 'Everyone',
  'MUTUAL_FOLLOW_FRIENDS': 'Friends',
  'FOLLOWER_OF_CREATOR': 'Followers',
  'SELF_ONLY': 'Only me',
};

const _tiktokMusicUrl =
    'https://www.tiktok.com/legal/page/global/music-usage-confirmation/en';
const _tiktokBrandedUrl = 'https://www.tiktok.com/legal/page/global/bc-policy/en';

/// The TikTok form state. `disclose` is UI-only; the API gets the two flags.
class _TikTokOptions {
  String privacyLevel = '';
  bool allowComment = false;
  bool allowDuet = false;
  bool allowStitch = false;
  bool disclose = false;
  bool brandOrganic = false;
  bool brandedContent = false;

  Map<String, dynamic> toJson() => {
    'privacy_level': privacyLevel,
    'allow_comment': allowComment,
    'allow_duet': allowDuet,
    'allow_stitch': allowStitch,
    'brand_organic': disclose && brandOrganic,
    'branded_content': disclose && brandedContent,
  };

  /// Why the post cannot be sent yet; empty when it can. Mirrors the web.
  String blocker(TikTokCreatorInfo? info) {
    if (info == null) return 'Loading your TikTok settings…';
    if (privacyLevel.isEmpty) return 'Choose who can view this video';
    if (disclose && !brandOrganic && !brandedContent) {
      return 'Pick what this video promotes';
    }
    if (disclose && brandedContent && privacyLevel == 'SELF_ONLY') {
      return 'Branded content cannot be private';
    }
    return '';
  }
}

class _YouTubeOptions {
  _YouTubeOptions(Clip clip)
    : title = _clampChars(clip.take.isEmpty ? 'Untitled BanterClips video' : clip.take, 100),
      description = '${clip.take} 😤 #${clip.sport.isEmpty ? 'Sports' : clip.sport} #HotTake #BanterClips';

  String title;
  String description;
  String privacyStatus = '';

  static String _clampChars(String text, int max) {
    final runes = text.runes.toList();
    return runes.length <= max ? text : String.fromCharCodes(runes.take(max));
  }

  int get titleLength => title.runes.length;
  int get descriptionBytes => utf8.encode(description).length;

  Map<String, dynamic> toJson() => {
    'title': title,
    'description': description,
    'privacy_status': privacyStatus,
  };

  String get blocker {
    if (title.trim().isEmpty) return 'Add a YouTube title';
    if (titleLength > 100) return 'Shorten the YouTube title';
    if (title.contains('<') || title.contains('>')) {
      return 'Remove < or > from the title';
    }
    if (descriptionBytes > 5000) return 'Shorten the YouTube description';
    if (description.contains('<') || description.contains('>')) {
      return 'Remove < or > from the description';
    }
    if (privacyStatus.isEmpty) return 'Choose YouTube visibility';
    return '';
  }
}

class _PublishSheet extends ConsumerStatefulWidget {
  const _PublishSheet({required this.clip, this.initialPlatform});

  final Clip clip;
  final String? initialPlatform;

  @override
  ConsumerState<_PublishSheet> createState() => _PublishSheetState();
}

class _PublishSheetState extends ConsumerState<_PublishSheet> {
  late final TextEditingController _caption = TextEditingController(
    text: '${widget.clip.take} 😤 #${widget.clip.sport} #HotTake #BanterClips',
  );
  late final _youtube = _YouTubeOptions(widget.clip);
  late final TextEditingController _ytTitle = TextEditingController(
    text: _youtube.title,
  );
  late final TextEditingController _ytDescription = TextEditingController(
    text: _youtube.description,
  );
  final _tiktok = _TikTokOptions();

  late String _platform;
  List<String> _suggestions = const [];

  /// Everything shown so far, sent back on regenerate so new options are
  /// genuinely new rather than a reshuffle of the same three.
  final List<String> _seen = [];
  bool _loadingSuggestions = true;
  bool _publishing = false;
  String _error = '';

  TikTokCreatorInfo? _creatorInfo;
  bool _loadingCreator = false;
  String _creatorError = '';

  /// The publishes for this clip, refreshed while one is in flight.
  late List<Publish> _publishes = widget.clip.publishes;
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    final state = ref.read(appStateProvider);
    final initial = widget.initialPlatform;
    _platform = initial != null && _platforms.any((p) => p.$1 == initial)
        ? initial
        : state.instagram != null
        ? 'instagram'
        : state.tiktok != null
        ? 'tiktok'
        : state.youtube != null
        ? 'youtube'
        : 'instagram';
    _fetchSuggestions();
    _maybeLoadCreatorInfo();
    _syncPolling();
  }

  @override
  void dispose() {
    _caption.dispose();
    _ytTitle.dispose();
    _ytDescription.dispose();
    _poll?.cancel();
    super.dispose();
  }

  Publish? _publishFor(String platform) {
    for (final p in _publishes) {
      if (p.platform == platform) return p;
    }
    return null;
  }

  bool get _anyInFlight => _publishes.any((p) => p.inFlight);

  void _syncPolling() {
    if (_anyInFlight) {
      _poll ??= Timer.periodic(const Duration(seconds: 4), (_) async {
        try {
          final fresh = await ref.read(apiClientProvider).getClip(widget.clip.id);
          if (!mounted) return;
          setState(() => _publishes = fresh.publishes);
          ref.read(appStateProvider.notifier).mergeClip(fresh);
          _syncPolling();
        } on ApiException {
          // transient — keep polling
        }
      });
    } else {
      _poll?.cancel();
      _poll = null;
    }
  }

  Future<void> _maybeLoadCreatorInfo() async {
    if (_platform != 'tiktok' || ref.read(appStateProvider).tiktok == null) {
      return;
    }
    setState(() {
      _loadingCreator = true;
      _creatorError = '';
    });
    try {
      final info = await ref.read(apiClientProvider).tiktokCreatorInfo();
      if (!mounted) return;
      setState(() {
        _creatorInfo = info;
        // With one option there is nothing to choose; pick it.
        if (info.privacyLevelOptions.length == 1) {
          _tiktok.privacyLevel = info.privacyLevelOptions.first;
        }
      });
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _creatorInfo = null;
          _creatorError = e.message;
        });
      }
    } finally {
      if (mounted) setState(() => _loadingCreator = false);
    }
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

  String get _blocker {
    final account = ref.read(appStateProvider).social(_platform);
    if (account == null) return '';
    if (_platform == 'tiktok') return _tiktok.blocker(_creatorInfo);
    if (_platform == 'youtube') return _youtube.blocker;
    return '';
  }

  Future<void> _publish() async {
    final account = ref.read(appStateProvider).social(_platform);
    if (account == null || _blocker.isNotEmpty) return;
    setState(() {
      _publishing = true;
      _error = '';
    });
    try {
      final publish = await ref
          .read(apiClientProvider)
          .publishClip(
            clipId: widget.clip.id,
            socialAccountId: account.id,
            caption: _platform == 'youtube' ? '' : _caption.text,
            tiktok: _platform == 'tiktok' ? _tiktok.toJson() : null,
            youtube: _platform == 'youtube' ? _youtube.toJson() : null,
          );
      unawaited(ref.read(appStateProvider.notifier).refreshClips());
      if (!mounted) return;
      setState(() {
        _publishes = [
          Publish(
            id: publish.id,
            clipId: publish.clipId,
            socialAccountId: publish.socialAccountId,
            caption: publish.caption,
            status: publish.status,
            error: publish.error,
            externalUrl: publish.externalUrl,
            platform: publish.platform ?? _platform,
            handle: publish.handle ?? account.handle,
            createdAt: publish.createdAt,
            publishedAt: publish.publishedAt,
          ),
          ..._publishes.where((p) => p.platform != _platform),
        ];
      });
      _syncPolling();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _publishing = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appStateProvider);
    final account = state.social(_platform);
    final connected = account != null;
    final name = platformName(_platform);
    final verb = switch (_platform) {
      'tiktok' => 'Post',
      'youtube' => 'Upload',
      _ => 'Publish',
    };
    final current = _publishFor(_platform);
    final blocker = _blocker;

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              'Publish clip',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 14),

            // ---- platform picker ------------------------------------------
            Row(
              children: [
                for (final (key, label, _) in _platforms) ...[
                  Expanded(
                    child: _PlatformTile(
                      platform: key,
                      label: label,
                      selected: _platform == key,
                      account: state.social(key),
                      publish: _publishFor(key),
                      onTap: () {
                        setState(() {
                          _platform = key;
                          _error = '';
                        });
                        _maybeLoadCreatorInfo();
                      },
                    ),
                  ),
                  if (key != 'youtube') const SizedBox(width: 8),
                ],
              ],
            ),
            const SizedBox(height: 16),

            // ---- destination ------------------------------------------------
            if (!connected) ...[
              SocialConnectCard(platform: _platform),
            ] else
              Text.rich(
                TextSpan(
                  style: const TextStyle(fontSize: 12.5, color: AppColors.muted),
                  children: [
                    TextSpan(
                      text: _platform == 'youtube'
                          ? 'Uploading to '
                          : _platform == 'tiktok'
                          ? 'Posting to '
                          : 'Publishing to ',
                    ),
                    TextSpan(
                      text: account.handle,
                      style: const TextStyle(
                        fontWeight: FontWeight.w700,
                        color: AppColors.text,
                      ),
                    ),
                    TextSpan(
                      text:
                          ' — ${_platforms.firstWhere((p) => p.$1 == _platform).$3}.',
                    ),
                  ],
                ),
              ),

            // ---- caption (Instagram + TikTok) -------------------------------
            if (_platform != 'youtube') ...[
              const SizedBox(height: 16),
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
                onChanged: (_) => setState(() {}),
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
            ],

            // ---- YouTube form ---------------------------------------------
            if (_platform == 'youtube' && connected) ...[
              const SizedBox(height: 16),
              _YouTubeForm(
                clip: widget.clip,
                handle: account.handle,
                options: _youtube,
                title: _ytTitle,
                description: _ytDescription,
                onChanged: () => setState(() {
                  _youtube.title = _ytTitle.text;
                  _youtube.description = _ytDescription.text;
                }),
                onPrivacy: (value) =>
                    setState(() => _youtube.privacyStatus = value),
              ),
            ],

            // ---- TikTok form ----------------------------------------------
            if (_platform == 'tiktok' && connected) ...[
              const SizedBox(height: 16),
              _TikTokForm(
                info: _creatorInfo,
                loading: _loadingCreator,
                error: _creatorError,
                options: _tiktok,
                onRetry: _maybeLoadCreatorInfo,
                onChanged: () => setState(() {}),
              ),
            ],

            if (widget.clip.watermarked) ...[
              const SizedBox(height: 14),
              const Notice(
                text:
                    'Free plan: your clip publishes with the BanterClips '
                    'watermark. Creator publishes clean.',
                icon: Icons.info_outline_rounded,
              ),
            ],
            if (_error.isNotEmpty) ...[
              const SizedBox(height: 12),
              Notice.error(_error),
            ],
            if (_platform == 'tiktok' && connected && _creatorInfo != null) ...[
              const SizedBox(height: 12),
              _TikTokLegalLine(branded: _tiktok.disclose && _tiktok.brandedContent),
            ],

            const SizedBox(height: 18),
            GradButton(
              label: !connected
                  ? 'Connect $name first'
                  : blocker.isNotEmpty
                  ? blocker
                  : current?.inFlight ?? false
                  ? '${verb}ing to $name…'
                  : current?.isPublished ?? false
                  ? '$verb to $name again'
                  : '$verb to $name',
              loading: _publishing,
              onPressed:
                  connected &&
                      blocker.isEmpty &&
                      !(current?.inFlight ?? false)
                  ? _publish
                  : null,
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextAction(
                  label: 'Done',
                  color: AppColors.muted,
                  onPressed: () => Navigator.of(context).pop(),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _PlatformTile extends StatelessWidget {
  const _PlatformTile({
    required this.platform,
    required this.label,
    required this.selected,
    required this.account,
    required this.publish,
    required this.onTap,
  });

  final String platform;
  final String label;
  final bool selected;
  final SocialAccount? account;
  final Publish? publish;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final (statusText, statusColor) = publish == null
        ? account == null
              ? ('Not connected', AppColors.muted2)
              : ('● ${account!.handle}', AppColors.green)
        : publish!.isPublished
        ? ('✓ Published', AppColors.green)
        : publish!.inFlight
        ? ('Publishing…', AppColors.cyan)
        : publish!.hasFailed
        ? ('Failed — retry free', AppColors.error)
        : (publish!.status, AppColors.muted);

    return AppPanel(
      onTap: onTap,
      color: selected ? AppColors.cyanWash(0.10) : AppColors.panel,
      borderColor: selected ? AppColors.cyan : AppColors.border,
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              PlatformBadge(platform: platform, size: 22),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  label,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppColors.text,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            statusText,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            style: TextStyle(fontSize: 10.5, color: statusColor),
          ),
        ],
      ),
    );
  }
}

/// The little platform mark — Instagram's gradient, TikTok's black tile,
/// YouTube's red — used by the picker and the connect cards.
class PlatformBadge extends StatelessWidget {
  const PlatformBadge({super.key, required this.platform, this.size = 28});

  final String platform;
  final double size;

  @override
  Widget build(BuildContext context) => Container(
    width: size,
    height: size,
    decoration: BoxDecoration(
      gradient: platform == 'instagram' ? AppColors.instagram : null,
      color: switch (platform) {
        'youtube' => const Color(0xFFFF0033),
        'tiktok' => const Color(0xFF010101),
        _ => AppColors.panel,
      },
      borderRadius: BorderRadius.circular(size * 0.3),
      border: platform == 'tiktok' ? Border.all(color: AppColors.border) : null,
    ),
    child: Icon(
      switch (platform) {
        'instagram' => Icons.camera_alt_outlined,
        'tiktok' => Icons.music_note_rounded,
        'youtube' => Icons.play_arrow_rounded,
        _ => Icons.link,
      },
      color: Colors.white,
      size: size * 0.6,
    ),
  );
}

class _YouTubeForm extends StatelessWidget {
  const _YouTubeForm({
    required this.clip,
    required this.handle,
    required this.options,
    required this.title,
    required this.description,
    required this.onChanged,
    required this.onPrivacy,
  });

  final Clip clip;
  final String handle;
  final _YouTubeOptions options;
  final TextEditingController title;
  final TextEditingController description;
  final VoidCallback onChanged;
  final ValueChanged<String> onPrivacy;

  static const _visibility = [
    ('public', 'Public', 'Anyone can watch'),
    ('unlisted', 'Unlisted', 'Anyone with the link'),
    ('private', 'Private', 'Only you'),
  ];

  @override
  Widget build(BuildContext context) {
    final badTitle = options.title.contains('<') || options.title.contains('>');
    final badDescription =
        options.description.contains('<') || options.description.contains('>');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AppPanel(
          child: Row(
            children: [
              const PlatformBadge(platform: 'youtube', size: 30),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Review your YouTube upload',
                      style: TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w700,
                        color: AppColors.text,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      'Destination: $handle · uploads as a Short',
                      style: const TextStyle(
                        fontSize: 11.5,
                        color: AppColors.muted,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 14),
        SectionLabel(
          'TITLE',
          trailing: Text(
            '${options.titleLength}/100',
            style: TextStyle(
              fontSize: 11,
              color: options.titleLength > 100 || badTitle
                  ? AppColors.error
                  : AppColors.muted2,
            ),
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: title,
          onChanged: (_) => onChanged(),
          decoration: const InputDecoration(hintText: 'Video title'),
        ),
        if (badTitle)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text(
              'YouTube titles cannot contain < or >.',
              style: TextStyle(fontSize: 11.5, color: AppColors.error),
            ),
          ),
        const SizedBox(height: 14),
        SectionLabel(
          'DESCRIPTION',
          trailing: Text(
            '${options.descriptionBytes}/5000 bytes',
            style: TextStyle(
              fontSize: 11,
              color: options.descriptionBytes > 5000 || badDescription
                  ? AppColors.error
                  : AppColors.muted2,
            ),
          ),
        ),
        const SizedBox(height: 8),
        TextField(
          controller: description,
          minLines: 3,
          maxLines: 6,
          onChanged: (_) => onChanged(),
          decoration: const InputDecoration(
            hintText: 'Tell viewers about this video',
          ),
        ),
        if (badDescription)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text(
              'YouTube descriptions cannot contain < or >.',
              style: TextStyle(fontSize: 11.5, color: AppColors.error),
            ),
          ),
        const SizedBox(height: 14),
        const SectionLabel('VISIBILITY · CHOOSE ONE'),
        const SizedBox(height: 8),
        Row(
          children: [
            for (final (key, label, sub) in _visibility) ...[
              Expanded(
                child: AppPanel(
                  onTap: () => onPrivacy(key),
                  color: options.privacyStatus == key
                      ? AppColors.cyanWash(0.10)
                      : AppColors.panel,
                  borderColor: options.privacyStatus == key
                      ? AppColors.cyan
                      : AppColors.border,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 10,
                  ),
                  child: Column(
                    children: [
                      Text(
                        label,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: options.privacyStatus == key
                              ? AppColors.cyan
                              : AppColors.text,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        sub,
                        textAlign: TextAlign.center,
                        maxLines: 2,
                        style: const TextStyle(
                          fontSize: 10,
                          color: AppColors.muted2,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
              if (key != 'private') const SizedBox(width: 8),
            ],
          ],
        ),
        const SizedBox(height: 10),
        const _YouTubeTermsLine(),
      ],
    );
  }
}

class _YouTubeTermsLine extends StatelessWidget {
  const _YouTubeTermsLine();

  @override
  Widget build(BuildContext context) => Wrap(
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      const Text(
        'Uses YouTube API Services · ',
        style: TextStyle(fontSize: 10.5, color: AppColors.muted2),
      ),
      _Link('YouTube Terms of Service', 'https://www.youtube.com/t/terms'),
      const Text(
        ' · ',
        style: TextStyle(fontSize: 10.5, color: AppColors.muted2),
      ),
      _Link('Google Privacy Policy', 'https://policies.google.com/privacy'),
    ],
  );
}

class _TikTokForm extends StatelessWidget {
  const _TikTokForm({
    required this.info,
    required this.loading,
    required this.error,
    required this.options,
    required this.onRetry,
    required this.onChanged,
  });

  final TikTokCreatorInfo? info;
  final bool loading;
  final String error;
  final _TikTokOptions options;
  final VoidCallback onRetry;
  final VoidCallback onChanged;

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const AppPanel(
        child: Row(
          children: [
            InlineSpinner(size: 14),
            SizedBox(width: 10),
            Text(
              'Loading your TikTok settings…',
              style: TextStyle(fontSize: 12.5, color: AppColors.muted),
            ),
          ],
        ),
      );
    }
    if (error.isNotEmpty) {
      return AppPanel(
        child: Row(
          children: [
            Expanded(
              child: Text(
                error,
                style: const TextStyle(fontSize: 12.5, color: AppColors.error),
              ),
            ),
            TextAction(label: 'Retry', fontSize: 12.5, onPressed: onRetry),
          ],
        ),
      );
    }
    final data = info;
    if (data == null) return const SizedBox.shrink();

    final branded = options.disclose && options.brandedContent;
    final labelText = branded
        ? 'Paid partnership'
        : options.disclose && options.brandOrganic
        ? 'Promotional content'
        : '';

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AppPanel(
          child: Row(
            children: [
              ClipOval(
                child: SizedBox(
                  width: 34,
                  height: 34,
                  child: data.avatarUrl.isEmpty
                      ? const ColoredBox(color: AppColors.border)
                      : Image.network(
                          data.avatarUrl,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) =>
                              const ColoredBox(color: AppColors.border),
                        ),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      data.nickname.isEmpty
                          ? 'Your TikTok account'
                          : data.nickname,
                      style: const TextStyle(
                        fontSize: 13.5,
                        fontWeight: FontWeight.w600,
                        color: AppColors.text,
                      ),
                    ),
                    if (data.username.isNotEmpty)
                      Text(
                        '@${data.username}',
                        style: const TextStyle(
                          fontSize: 11.5,
                          color: AppColors.muted2,
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
        if (data.unaudited) ...[
          const SizedBox(height: 10),
          const Notice(
            text:
                "BanterClips is under TikTok's app review. Until it clears, "
                'TikTok accepts posts only as "Only me", and only from a '
                'private TikTok account — any other audience is rejected.',
            icon: Icons.info_outline_rounded,
          ),
        ],
        const SizedBox(height: 14),
        const SectionLabel('WHO CAN VIEW THIS VIDEO'),
        const SizedBox(height: 8),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            for (final level in data.privacyLevelOptions)
              AppChip(
                label: _tiktokPrivacyLabels[level] ?? level,
                selected: options.privacyLevel == level,
                locked: branded && level == 'SELF_ONLY',
                onTap: branded && level == 'SELF_ONLY'
                    ? null
                    : () {
                        options.privacyLevel = level;
                        onChanged();
                      },
              ),
          ],
        ),
        if (branded)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text(
              '"Only me" is not available for branded content.',
              style: TextStyle(fontSize: 11.5, color: AppColors.muted2),
            ),
          ),
        const SizedBox(height: 14),
        const SectionLabel('ALLOW USERS TO'),
        const SizedBox(height: 4),
        _Check(
          label: 'Comment',
          value: options.allowComment,
          disabled: data.commentDisabled,
          note: data.commentDisabled
              ? 'You have turned comments off in your TikTok settings'
              : null,
          onChanged: (v) {
            options.allowComment = v;
            onChanged();
          },
        ),
        _Check(
          label: 'Duet',
          value: options.allowDuet,
          disabled: data.duetDisabled,
          note: data.duetDisabled
              ? 'You have turned Duet off in your TikTok settings'
              : null,
          onChanged: (v) {
            options.allowDuet = v;
            onChanged();
          },
        ),
        _Check(
          label: 'Stitch',
          value: options.allowStitch,
          disabled: data.stitchDisabled,
          note: data.stitchDisabled
              ? 'You have turned Stitch off in your TikTok settings'
              : null,
          onChanged: (v) {
            options.allowStitch = v;
            onChanged();
          },
        ),
        const SizedBox(height: 10),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Disclose video content',
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: AppColors.text,
                    ),
                  ),
                  SizedBox(height: 2),
                  Text(
                    'Turn on to disclose that this video promotes goods or '
                    'services in exchange for something of value. Your video '
                    'could promote yourself, a third party, or both.',
                    style: TextStyle(
                      fontSize: 11.5,
                      height: 1.45,
                      color: AppColors.muted2,
                    ),
                  ),
                ],
              ),
            ),
            Switch(
              value: options.disclose,
              onChanged: (v) {
                options.disclose = v;
                if (!v) {
                  options.brandOrganic = false;
                  options.brandedContent = false;
                }
                onChanged();
              },
            ),
          ],
        ),
        if (options.disclose) ...[
          _Check(
            label: 'Your brand',
            value: options.brandOrganic,
            note:
                'You are promoting yourself or your own business. This video '
                'will be classified as Brand Organic.',
            onChanged: (v) {
              options.brandOrganic = v;
              onChanged();
            },
          ),
          _Check(
            label: 'Branded content',
            value: options.brandedContent,
            note:
                'You are promoting another brand or a third party. This '
                'video will be classified as Branded Content.',
            onChanged: (v) {
              options.brandedContent = v;
              if (v && options.privacyLevel == 'SELF_ONLY') {
                options.privacyLevel = '';
              }
              onChanged();
            },
          ),
          if (labelText.isNotEmpty) ...[
            const SizedBox(height: 6),
            Notice(
              text:
                  'Your video will be labeled "$labelText". This cannot be '
                  'changed once you post.',
              icon: Icons.label_outline_rounded,
            ),
          ],
        ],
      ],
    );
  }
}

class _Check extends StatelessWidget {
  const _Check({
    required this.label,
    required this.value,
    required this.onChanged,
    this.disabled = false,
    this.note,
  });

  final String label;
  final bool value;
  final bool disabled;
  final String? note;
  final ValueChanged<bool> onChanged;

  @override
  Widget build(BuildContext context) => Opacity(
    opacity: disabled ? 0.45 : 1,
    child: InkWell(
      onTap: disabled ? null : () => onChanged(!value),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SizedBox(
              width: 24,
              height: 24,
              child: Checkbox(
                value: value,
                onChanged: disabled ? null : (v) => onChanged(v ?? false),
                activeColor: AppColors.cyan,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    label,
                    style: const TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: AppColors.text,
                    ),
                  ),
                  if (note != null)
                    Text(
                      note!,
                      style: const TextStyle(
                        fontSize: 11.5,
                        height: 1.4,
                        color: AppColors.muted2,
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    ),
  );
}

class _TikTokLegalLine extends StatelessWidget {
  const _TikTokLegalLine({required this.branded});

  final bool branded;

  @override
  Widget build(BuildContext context) => Wrap(
    alignment: WrapAlignment.center,
    crossAxisAlignment: WrapCrossAlignment.center,
    children: [
      const Text(
        "By posting, you agree to TikTok's ",
        style: TextStyle(fontSize: 11, color: AppColors.muted2),
      ),
      if (branded) ...[
        _Link('Branded Content Policy', _tiktokBrandedUrl),
        const Text(
          ' and ',
          style: TextStyle(fontSize: 11, color: AppColors.muted2),
        ),
      ],
      _Link('Music Usage Confirmation', _tiktokMusicUrl),
      const Text('.', style: TextStyle(fontSize: 11, color: AppColors.muted2)),
    ],
  );
}

class _Link extends StatelessWidget {
  const _Link(this.label, this.url);

  final String label;
  final String url;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: () =>
        launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication),
    borderRadius: BorderRadius.circular(AppTheme.radiusChip),
    child: Text(
      label,
      style: const TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w600,
        color: AppColors.cyan,
      ),
    ),
  );
}
