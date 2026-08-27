import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';

import '../../api/errors.dart';
import '../../app/env.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';

/// The one Instagram connect/disconnect control in the app. Used by both
/// Account and the last step of onboarding.
///
/// The mobile OAuth flow differs from the web's in one way that matters: a
/// phone has no browser tab to return to. So instead of a full-page redirect,
/// Meta's consent screen opens in a system browser sheet
/// (ASWebAuthenticationSession on iOS, Custom Tabs on Android) and control
/// comes back through a redirect the app owns — `banterclips://oauth/instagram`.
///
/// That requires two things outside this file:
///   1. the scheme registered in AndroidManifest.xml and Info.plist (done), and
///   2. the backend allow-listing it in the `next` parameter of
///      `GET /socials/instagram/oauth-url` — see mobile/README.md, which
///      carries the exact patch. Until that lands, the backend falls back to
///      `/account` on the website and this flow ends in the browser rather
///      than back in the app; the account still connects, and pulling to
///      refresh Account picks it up.
class InstagramConnectCard extends ConsumerStatefulWidget {
  const InstagramConnectCard({super.key});

  @override
  ConsumerState<InstagramConnectCard> createState() => _InstagramConnectCardState();
}

class _InstagramConnectCardState extends ConsumerState<InstagramConnectCard> {
  bool _busy = false;
  String _error = '';

  Future<void> connect() async {
    setState(() {
      _busy = true;
      _error = '';
    });
    final api = ref.read(apiClientProvider);
    final notifier = ref.read(appStateProvider.notifier);
    try {
      String? url;
      try {
        url = await api.instagramOauthUrl(next: Env.igRedirect);
      } on ApiException catch (e) {
        // 503 means the Meta app isn't configured on this backend — fall
        // through to the mock connector, exactly as the web does.
        if (e.status != 503 && e.code != ApiCode.oauthNotConfigured) rethrow;
      }

      if (url != null && url.isNotEmpty) {
        await FlutterWebAuth2.authenticate(
          url: url,
          callbackUrlScheme: Env.oauthScheme,
        );
      } else {
        await api.connectSocial('instagram');
      }
      await notifier.refreshSocials();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } catch (e) {
      // The user dismissed the browser sheet — that is a choice, not a fault.
      final cancelled = e.toString().toLowerCase().contains('cancel');
      if (mounted && !cancelled) {
        setState(() => _error = 'Instagram connect did not complete. Try again.');
      }
      // Connect may still have succeeded server-side before the sheet closed.
      await notifier.refreshSocials();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> disconnect() async {
    setState(() {
      _busy = true;
      _error = '';
    });
    try {
      await ref.read(appStateProvider.notifier).disconnectInstagram();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(appStateProvider);
    final account = state.instagram;
    final connected = state.instagramConnected;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AppCard(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: const BoxDecoration(
                      gradient: AppColors.instagram,
                      shape: BoxShape.circle,
                    ),
                    child: const Icon(Icons.camera_alt_outlined, size: 20, color: Colors.white),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          connected ? 'Instagram · ${account!.handle}' : 'Instagram',
                          style: Theme.of(context).textTheme.titleSmall,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          connected
                              ? '● Connected — clips publish as Reels'
                              : 'Not connected',
                          style: TextStyle(
                            fontSize: 12,
                            color: connected ? AppColors.green : AppColors.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 16),
              if (connected)
                GhostButton(
                  label: 'Disconnect',
                  loading: _busy,
                  color: AppColors.muted,
                  height: 44,
                  onPressed: disconnect,
                )
              else
                GradButton(
                  label: 'Connect Instagram',
                  loading: _busy,
                  height: 46,
                  onPressed: connect,
                ),
            ],
          ),
        ),
        if (_error.isNotEmpty) ...[
          const SizedBox(height: 12),
          Notice.error(_error),
        ],
      ],
    );
  }
}
