import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import '../../api/errors.dart';
import '../../app/env.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';
import '../clips/publish_sheet.dart' show PlatformBadge;

class InstagramConnectCard extends StatelessWidget {
  const InstagramConnectCard({super.key});
  @override
  Widget build(BuildContext context) =>
      const SocialConnectCard(platform: 'instagram');
}

class SocialConnectCard extends ConsumerStatefulWidget {
  const SocialConnectCard({required this.platform, super.key});
  final String platform;
  @override
  ConsumerState<SocialConnectCard> createState() => _SocialConnectCardState();
}

class _SocialConnectCardState extends ConsumerState<SocialConnectCard> {
  bool busy = false;
  String error = '';
  String get name => switch (widget.platform) {
    'instagram' => 'Instagram',
    'tiktok' => 'TikTok',
    'youtube' => 'YouTube',
    _ => widget.platform,
  };
  String get destination => switch (widget.platform) {
    'instagram' => 'clips publish as Reels · explicit per-clip publishing only',
    'tiktok' => 'clips post to your TikTok · explicit per-clip publishing only',
    'youtube' => 'clips upload as Shorts · explicit per-clip publishing only',
    _ => 'connected',
  };

  Future<void> connect() async {
    setState(() {
      busy = true;
      error = '';
    });
    final api = ref.read(apiClientProvider);
    try {
      String? url;
      try {
        url = await api.socialOauthUrl(
          widget.platform,
          next: '${Env.oauthScheme}://oauth/${widget.platform}',
        );
      } on ApiException catch (e) {
        if (e.status != 503 && e.code != ApiCode.oauthNotConfigured) rethrow;
      }
      if (url != null && url.isNotEmpty) {
        await FlutterWebAuth2.authenticate(
          url: url,
          callbackUrlScheme: Env.oauthScheme,
        );
      } else {
        await api.connectSocial(widget.platform);
      }
      await ref.read(appStateProvider.notifier).refreshSocials();
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } catch (e) {
      if (mounted && !e.toString().toLowerCase().contains('cancel')) {
        setState(() => error = '$name connection did not complete. Try again.');
      }
      await ref.read(appStateProvider.notifier).refreshSocials();
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> disconnect() async {
    setState(() {
      busy = true;
      error = '';
    });
    try {
      await ref
          .read(appStateProvider.notifier)
          .disconnectSocial(widget.platform);
    } on ApiException catch (e) {
      if (mounted) setState(() => error = e.message);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final account = ref.watch(appStateProvider).social(widget.platform);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  PlatformBadge(platform: widget.platform, size: 40),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          account == null ? name : '$name · ${account.handle}',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          account == null
                              ? 'Not connected'
                              : '● Connected — $destination',
                          style: TextStyle(
                            fontSize: 12,
                            color: account == null
                                ? AppColors.muted
                                : AppColors.green,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (account == null)
                GradButton(
                  label: 'Connect $name',
                  loading: busy,
                  height: 46,
                  onPressed: connect,
                )
              else
                GhostButton(
                  label: 'Disconnect',
                  loading: busy,
                  color: AppColors.muted,
                  height: 44,
                  onPressed: disconnect,
                ),
              if (widget.platform == 'youtube')
                const Padding(
                  padding: EdgeInsets.only(top: 10),
                  child: Text(
                    'Uses YouTube API Services · YouTube Terms of Service · Google Privacy Policy',
                    style: TextStyle(
                      fontSize: 10.5,
                      height: 1.45,
                      color: AppColors.muted2,
                    ),
                  ),
                ),
            ],
          ),
        ),
        if (error.isNotEmpty) ...[
          const SizedBox(height: 10),
          Notice.error(error),
        ],
      ],
    );
  }
}
