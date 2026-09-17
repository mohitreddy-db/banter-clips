import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../api/errors.dart';
import '../../app/env.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';
import 'instagram_connect.dart';
import 'top_up_sheet.dart';
import 'upgrade_sheet.dart';

/// Account — the port of `frontend/src/pages/Account.jsx`.
///
/// Usage, plan, connected accounts, preferences, legal links, sign out.
///
/// The plan section links out to the website rather than selling here. That
/// is a deliberate v1 decision, not an oversight: a subscription consumed
/// inside the app has to go through store billing (Apple 3.1.1), which takes
/// 15–30% on top of margins that `UNIT-ECONOMICS.md` already calls thin.
/// Shipping free-tier-first defers that whole problem — and the paywall work
/// — to a version that can price for it.
class AccountScreen extends ConsumerWidget {
  const AccountScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(appStateProvider);
    final user = state.user;
    final prefs = user?.preferences;

    return Scaffold(
      appBar: AppBar(title: const Text('Account')),
      body: RefreshIndicator(
        onRefresh: () => ref.read(appStateProvider.notifier).refreshUser(),
        color: AppColors.cyan,
        backgroundColor: AppColors.surface,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
          children: [
            // ---- profile ------------------------------------------------
            AppCard(
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: const BoxDecoration(
                      gradient: AppColors.instagram,
                      shape: BoxShape.circle,
                    ),
                    child: Center(
                      child: Text(
                        user?.initial ?? '?',
                        style: const TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w700,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          user?.email ?? '',
                          style: Theme.of(context).textTheme.titleMedium,
                          overflow: TextOverflow.ellipsis,
                        ),
                        const SizedBox(height: 3),
                        Text(
                          [
                            'Beta creator',
                            if ((prefs?.role ?? '').isNotEmpty) prefs!.role!,
                            if (user?.createdAt != null)
                              'joined ${_joined(user!.createdAt!)}',
                          ].join(' · '),
                          style: const TextStyle(
                            fontSize: 12.5,
                            color: AppColors.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            if (user?.isAdmin == true) ...[
              AppCard(
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(
                    Icons.admin_panel_settings_outlined,
                    color: AppColors.cyan,
                  ),
                  title: const Text('Admin Console'),
                  subtitle: const Text(
                    'Live operations, graphs, costs, revenue and audit log.',
                  ),
                  trailing: const Icon(
                    Icons.arrow_forward_ios_rounded,
                    size: 16,
                  ),
                  onTap: () => context.push('/admin'),
                ),
              ),
              const SizedBox(height: 16),
            ],

            // ---- plan & credits -----------------------------------------
            // The port of the web's PLAN & CREDITS card: the wallet, what it
            // buys, a top-up, and — on Creator — where the subscription is
            // managed. Never "X of Y videos": credits are the only unit.
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionLabel(
                    'PLAN & CREDITS',
                    trailing: Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 12,
                        vertical: 4,
                      ),
                      decoration: BoxDecoration(
                        color: state.isCreator
                            ? AppColors.greenWash(0.14)
                            : AppColors.chipOff,
                        borderRadius: BorderRadius.circular(
                          AppTheme.radiusPill,
                        ),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Text(
                        state.isCreator ? 'CREATOR' : 'FREE',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: state.isCreator
                              ? AppColors.green
                              : AppColors.muted,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        '⚡ ${state.credits}',
                        style: const TextStyle(
                          fontSize: 30,
                          fontWeight: FontWeight.w800,
                          color: AppColors.text,
                        ),
                      ),
                      const SizedBox(width: 8),
                      const Padding(
                        padding: EdgeInsets.only(bottom: 4),
                        child: Text(
                          'credits available',
                          style: TextStyle(
                            fontSize: 14,
                            color: AppColors.muted,
                          ),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 10),
                  Text(
                    '≈ ${state.credits ~/ state.videoPrice(15, '720p')} videos at 15s Standard'
                    '${state.isCreator ? ' · ≈ ${state.credits ~/ state.videoPrice(15, '1080p')} at 15s HD' : ''}'
                    ' · only successful videos charge — failures are refunded.',
                    style: const TextStyle(
                      fontSize: 12.5,
                      height: 1.5,
                      color: AppColors.muted,
                    ),
                  ),
                  const SizedBox(height: 16),
                  GradButton(
                    label: '⚡ Top up credits',
                    height: 46,
                    onPressed: () => showTopUpSheet(context),
                  ),
                  const SizedBox(height: 10),
                  if (!state.isCreator) ...[
                    GhostButton(
                      label:
                          'Creator plan — 1080p, 30s, 500-char prompts, no watermark, 150 credits/mo',
                      height: 54,
                      fontSize: 13,
                      onPressed: () => context.push('/plans'),
                    ),
                    // Somebody who reinstalls opens Account, not the paywall,
                    // and wonders where their plan went.
                    const RestorePurchasesRow(),
                  ] else ...[
                    if (user?.cancelAtPeriodEnd ?? false)
                      const Notice(
                        text:
                            'Creator stays active until the end of the billing period, '
                            'then you move to Free. Your videos are never deleted.',
                        icon: Icons.schedule_rounded,
                      )
                    else
                      // A store subscription can only be cancelled in the
                      // store — we are not allowed to do it for them, and
                      // pretending otherwise leaves people billed. Deep-link
                      // straight to the right settings screen; a web
                      // (Stripe) subscription is managed on the website.
                      GhostButton(
                        label: 'Manage subscription ↗',
                        color: AppColors.muted,
                        height: 46,
                        onPressed: () => _manageSubscription(ref),
                      ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ---- connected accounts -------------------------------------
            const SectionLabel('CONNECTED ACCOUNTS'),
            const SizedBox(height: 10),
            const InstagramConnectCard(),
            const SizedBox(height: 8),
            const SocialConnectCard(platform: 'tiktok'),
            const SizedBox(height: 8),
            const SocialConnectCard(platform: 'youtube'),
            const SizedBox(height: 8),
            const _ChannelCard(
              name: 'X',
              detail: 'Video post with caption · coming soon',
              icon: Icons.alternate_email_rounded,
            ),
            const SizedBox(height: 20),

            // ---- preferences --------------------------------------------
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  SectionLabel(
                    'STUDIO PREFERENCES',
                    trailing: TextAction(
                      label: 'Edit →',
                      fontSize: 12.5,
                      onPressed: () => context.push('/onboarding'),
                    ),
                  ),
                  const SizedBox(height: 12),
                  if (prefs == null || prefs.isEmpty)
                    const Text(
                      'Nothing picked yet — these pre-fill your Studio.',
                      style: TextStyle(fontSize: 13, color: AppColors.muted),
                    )
                  else
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: [
                        for (final tag in prefs.allTags)
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 7,
                            ),
                            decoration: BoxDecoration(
                              color: AppColors.chipOff,
                              borderRadius: BorderRadius.circular(
                                AppTheme.radiusChip,
                              ),
                              border: Border.all(color: AppColors.border),
                            ),
                            child: Text(
                              tag,
                              style: const TextStyle(
                                fontSize: 12.5,
                                color: AppColors.muted,
                              ),
                            ),
                          ),
                      ],
                    ),
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ---- data & privacy -----------------------------------------
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const SectionLabel('DATA & PRIVACY'),
                  const SizedBox(height: 10),
                  const Text(
                    'Your videos are private to your account and kept for 90 days '
                    'during beta. They are never made public without your consent.',
                    style: TextStyle(
                      fontSize: 13.5,
                      height: 1.55,
                      color: AppColors.muted,
                    ),
                  ),
                  const SizedBox(height: 12),
                  // Both stores require these to be reachable from inside the
                  // app. Opening the live pages is the sanctioned way to do
                  // it — rebuilding two legal documents natively buys nothing.
                  _LinkRow(
                    label: 'Privacy policy',
                    onTap: () => context.push('/privacy'),
                  ),
                  _LinkRow(
                    label: 'Terms of service',
                    onTap: () => context.push('/terms'),
                  ),
                  _LinkRow(
                    label: 'Report a clip or a problem',
                    onTap: () => context.go('/feedback'),
                  ),
                  _LinkRow(
                    label: 'Download my data',
                    onTap: () => _open('${Env.webUrl}/account'),
                  ),
                  _LinkRow(
                    label: 'Delete my account and videos',
                    onTap: () => _open('${Env.webUrl}/account'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            GhostButton(
              label: 'Sign out',
              color: AppColors.muted,
              onPressed: () => ref.read(appStateProvider.notifier).signOut(),
            ),
            const SizedBox(height: 16),
            const Center(
              child: Text(
                'BanterClips · beta',
                style: TextStyle(fontSize: 11.5, color: AppColors.muted2),
              ),
            ),
          ],
        ),
      ),
    );
  }

  static String _joined(DateTime at) {
    const months = [
      'Jan',
      'Feb',
      'Mar',
      'Apr',
      'May',
      'Jun',
      'Jul',
      'Aug',
      'Sep',
      'Oct',
      'Nov',
      'Dec',
    ];
    return '${months[at.month - 1]} ${at.year}';
  }

  static Future<void> _open(String url) =>
      launchUrl(Uri.parse(url), mode: LaunchMode.externalApplication);

  /// Where this Creator subscription is managed. A store subscription lives
  /// in the store's own settings; a website one in Stripe's portal, which
  /// the server hands us a URL for. Try the portal first: it 503s for
  /// anyone without a Stripe customer, which is exactly the store case.
  static Future<void> _manageSubscription(WidgetRef ref) async {
    try {
      final url = await ref.read(apiClientProvider).billingPortal();
      if (url != null && url.isNotEmpty) {
        await _open(url);
        return;
      }
    } on ApiException {
      // No Stripe billing for this account — fall through to the store.
    }
    await _open(
      Platform.isIOS
          ? 'https://apps.apple.com/account/subscriptions'
          : 'https://play.google.com/store/account/subscriptions',
    );
  }
}

class _LinkRow extends StatelessWidget {
  const _LinkRow({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: onTap,
    borderRadius: BorderRadius.circular(8),
    child: Padding(
      padding: const EdgeInsets.symmetric(vertical: 11),
      child: Row(
        children: [
          Expanded(
            child: Text(
              label,
              style: const TextStyle(
                fontSize: 13.5,
                fontWeight: FontWeight.w600,
                color: AppColors.cyan,
              ),
            ),
          ),
          const Icon(
            Icons.open_in_new_rounded,
            size: 15,
            color: AppColors.muted2,
          ),
        ],
      ),
    ),
  );
}

class _ChannelCard extends StatelessWidget {
  const _ChannelCard({
    required this.name,
    required this.detail,
    required this.icon,
  });

  final String name, detail;
  final IconData icon;

  @override
  Widget build(BuildContext context) => AppCard(
    child: Row(
      children: [
        Container(
          width: 38,
          height: 38,
          decoration: BoxDecoration(
            color: AppColors.panel,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Icon(icon, color: AppColors.text),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(name, style: const TextStyle(fontWeight: FontWeight.w700)),
              Text(
                detail,
                style: const TextStyle(fontSize: 11.5, color: AppColors.muted),
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
  );
}
