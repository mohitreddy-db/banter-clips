import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../app/env.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';

/// Why an action is locked. Wording changes; the offer does not.
enum UpgradeReason { limit, download, quality, duration }

/// The Creator upsell — the port of `UpgradeModal` in
/// `frontend/src/components/Modals.jsx`, as a bottom sheet.
///
/// **It does not sell anything.** A $9.99/month subscription consumed inside
/// the app is a digital good; Apple (Guideline 3.1.1) and Google both require
/// that to run through their billing, and a Stripe Checkout page opened from
/// here is a straightforward rejection. So v1 explains the plan and sends the
/// user to the website to buy — the "reader-style" split.
///
/// If native in-app purchase is adopted later, this is the one file that
/// changes: swap [_upgradeAction] for an `in_app_purchase` flow and verify
/// the receipt server-side before flipping `users.plan`. Never trust the
/// client's word that a purchase succeeded.
Future<void> showUpgradeSheet(BuildContext context, {required UpgradeReason reason}) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (context) => _UpgradeSheet(reason: reason),
    );

class _UpgradeSheet extends StatelessWidget {
  const _UpgradeSheet({required this.reason});

  final UpgradeReason reason;

  static const _features = [
    'Download in HD — no watermark',
    'Publish without the watermark',
    'Full HD 1080p quality',
    'Videos up to 30 seconds',
    '30 videos a month (vs 5)',
    'Priority render queue',
  ];

  String get _title => switch (reason) {
        UpgradeReason.limit => "You've hit this month's limit",
        UpgradeReason.download => 'Downloading is a Creator feature',
        UpgradeReason.quality => '1080p is a Creator feature',
        UpgradeReason.duration => 'Longer videos are a Creator feature',
      };

  @override
  Widget build(BuildContext context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Container(
                width: 52,
                height: 52,
                decoration: BoxDecoration(
                  color: AppColors.cyanWash(0.12),
                  borderRadius: BorderRadius.circular(16),
                ),
                child: const Icon(Icons.lock_open_rounded, color: AppColors.cyan, size: 24),
              ),
              const SizedBox(height: 16),
              Text(_title, style: Theme.of(context).textTheme.headlineSmall),
              const SizedBox(height: 10),
              Text(
                'On Free you publish with the BanterClips watermark — every post '
                'promotes you and us. Creator unlocks the full kit:',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 16),
              for (final feature in _features)
                Padding(
                  padding: const EdgeInsets.only(bottom: 9),
                  child: Row(
                    children: [
                      const Icon(Icons.check_rounded, size: 17, color: AppColors.green),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Text(
                          feature,
                          style: const TextStyle(
                            fontSize: 14,
                            fontWeight: FontWeight.w500,
                            color: AppColors.text,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 8),
              // Honest about where the transaction happens. Vague wording
              // here is what gets a build rejected under Guideline 3.1.1.
              const Notice(
                text: 'Plans are managed on banterclips.com. Upgrade there and '
                    'your account unlocks here straight away.',
                icon: Icons.open_in_new_rounded,
              ),
              const SizedBox(height: 16),
              GradButton(
                label: 'Upgrade on the web — \$9.99/mo',
                onPressed: () async {
                  Navigator.of(context).pop();
                  await launchUrl(
                    Uri.parse(Env.pricingUrl),
                    mode: LaunchMode.externalApplication,
                  );
                },
              ),
              const SizedBox(height: 8),
              TextAction(
                label: 'Maybe later',
                color: AppColors.muted,
                onPressed: () => Navigator.of(context).pop(),
              ),
            ],
          ),
        ),
      );
}
