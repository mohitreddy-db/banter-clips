import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import 'purchases.dart';

/// Why an action is locked. Wording changes; the offer does not.
enum UpgradeReason { limit, download, quality, duration, takeLength }

/// The Creator paywall — the port of `UpgradeModal` in
/// `frontend/src/components/Modals.jsx`, selling through the store rather
/// than Stripe.
///
/// The purchase logic all lives in [PurchaseController]; this file is the
/// presentation of it. The one rule worth repeating here: nothing on this
/// screen decides the user is a Creator. It shows what the server said after
/// it verified the receipt.
Future<void> showUpgradeSheet(
  BuildContext context, {
  required UpgradeReason reason,
}) => showModalBottomSheet<void>(
  context: context,
  isScrollControlled: true,
  backgroundColor: AppColors.surface,
  builder: (context) => _UpgradeSheet(reason: reason),
);

class _UpgradeSheet extends ConsumerStatefulWidget {
  const _UpgradeSheet({required this.reason});

  final UpgradeReason reason;

  @override
  ConsumerState<_UpgradeSheet> createState() => _UpgradeSheetState();
}

class _UpgradeSheetState extends ConsumerState<_UpgradeSheet> {
  static const _features = [
    'Download in HD — no watermark',
    'Publish without the watermark',
    'Full HD 1080p quality',
    'Videos up to 30 seconds',
    'Prompts up to 500 characters',
    '150 credits added every month',
    'Priority render queue',
  ];

  @override
  void initState() {
    super.initState();
    // Ask the store what this costs here, so the price shown is the price
    // charged — in the right currency, with the right regional tax.
    Future.microtask(
      () => ref.read(purchaseControllerProvider.notifier).loadProduct(),
    );
  }

  String get _title => switch (widget.reason) {
    UpgradeReason.limit => "You've hit this month's limit",
    UpgradeReason.download => 'Downloading is a Creator feature',
    UpgradeReason.quality => '1080p is a Creator feature',
    UpgradeReason.duration => 'Longer videos are a Creator feature',
    UpgradeReason.takeLength => 'Longer prompts are a Creator feature',
  };

  @override
  Widget build(BuildContext context) {
    final purchase = ref.watch(purchaseControllerProvider);
    final controller = ref.read(purchaseControllerProvider.notifier);

    if (purchase.phase == PurchasePhase.success) {
      return const _WelcomeToCreator();
    }

    return SafeArea(
      child: SingleChildScrollView(
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
              child: const Icon(
                Icons.lock_open_rounded,
                color: AppColors.cyan,
                size: 24,
              ),
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
                    const Icon(
                      Icons.check_rounded,
                      size: 17,
                      color: AppColors.green,
                    ),
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

            if (purchase.error.isNotEmpty) ...[
              const SizedBox(height: 8),
              Notice.error(purchase.error),
            ],

            const SizedBox(height: 18),

            GradButton(
              label: purchase.phase == PurchasePhase.unavailable
                  ? 'Retry secure payment'
                  : purchase.phase == PurchasePhase.verifying
                  ? 'Activating…'
                  : 'Upgrade to Creator — $creatorPriceLabel/mo',
              height: 54,
              loading: purchase.busy,
              onPressed: controller.buy,
            ),
            if (purchase.storePrice != null) ...[
              const SizedBox(height: 8),
              Text(
                // The store bills in local currency at the price set in its
                // console. Say so, so nobody is surprised by the receipt.
                'Billed by $storeName as ${purchase.storePrice}/month',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 12, color: AppColors.muted),
              ),
            ],

            const SizedBox(height: 12),

            TextAction(
              label: 'Refresh an existing subscription',
              color: AppColors.muted,
              fontSize: 13,
              onPressed: purchase.busy ? null : controller.restore,
            ),

            const SizedBox(height: 6),
            Text(
              'Secure payment by $storeName. Renews monthly until cancelled; '
              'manage or cancel it from your $storeSubscriptionsName.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 11,
                height: 1.5,
                color: AppColors.muted2,
              ),
            ),
            // App Store guideline 3.1.2 asks for the subscription's terms
            // and a link to the EULA and privacy policy on the screen that
            // sells it — not buried in Account. Both are root-level routes,
            // so they open above this sheet and it is still here on the way
            // back.
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                TextAction(
                  label: 'Terms of Use',
                  color: AppColors.muted,
                  fontSize: 11.5,
                  onPressed: () => context.push('/terms'),
                ),
                const Text(
                  '·',
                  style: TextStyle(fontSize: 11.5, color: AppColors.muted2),
                ),
                TextAction(
                  label: 'Privacy Policy',
                  color: AppColors.muted,
                  fontSize: 11.5,
                  onPressed: () => context.push('/privacy'),
                ),
              ],
            ),
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
}

class _WelcomeToCreator extends ConsumerWidget {
  const _WelcomeToCreator();

  @override
  Widget build(BuildContext context, WidgetRef ref) => SafeArea(
    child: Padding(
      padding: const EdgeInsets.fromLTRB(24, 12, 24, 24),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              color: AppColors.greenWash(0.14),
              borderRadius: BorderRadius.circular(18),
            ),
            child: const Center(
              child: Text('🎉', style: TextStyle(fontSize: 26)),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Welcome to Creator',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 10),
          Text(
            'Watermark-free publishing, HD downloads, 1080p and 150 credits a '
            'month are unlocked now.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 22),
          GradButton(
            label: 'Continue',
            onPressed: () {
              ref.read(purchaseControllerProvider.notifier).reset();
              Navigator.of(context).pop();
            },
          ),
        ],
      ),
    ),
  );
}

/// A small always-visible restore entry for the Account screen. Somebody who
/// reinstalls does not open the paywall — they open Account and wonder where
/// their plan went.
class RestorePurchasesRow extends ConsumerWidget {
  const RestorePurchasesRow({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final purchase = ref.watch(purchaseControllerProvider);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: purchase.busy
              ? null
              : () => ref.read(purchaseControllerProvider.notifier).restore(),
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 11),
            child: Row(
              children: [
                const Expanded(
                  child: Text(
                    'Refresh an existing subscription',
                    style: TextStyle(
                      fontSize: 13.5,
                      fontWeight: FontWeight.w600,
                      color: AppColors.cyan,
                    ),
                  ),
                ),
                if (purchase.phase == PurchasePhase.verifying)
                  const InlineSpinner(size: 14)
                else
                  const Icon(
                    Icons.refresh_rounded,
                    size: 16,
                    color: AppColors.muted2,
                  ),
              ],
            ),
          ),
        ),
        if (purchase.error.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: 6),
            child: Text(
              purchase.error,
              style: const TextStyle(fontSize: 12, color: AppColors.muted),
            ),
          ),
      ],
    );
  }
}
