import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/client.dart';
import '../../api/errors.dart';
import '../../state/app_state.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import 'purchases.dart';

/// Top up credits — the port of the web's top-up modal, selling through the
/// store rather than Stripe.
///
/// Credits are digital goods consumed inside the app, so Google (and Apple
/// 3.1.1) require in-app billing for them; opening a Stripe page from here
/// is a straightforward rejection. The packs and their credit amounts come
/// from `/billing/packs` so the two clients cannot drift; the price shown
/// is the store's own, in the customer's currency.
///
/// Out of credits → top up, never upgrade (PRICING.md rule 2). This sheet is
/// the only thing an empty wallet ever opens.
///
/// Except on iOS, where it explains itself instead of selling. The server
/// cannot yet verify an App Store consumable receipt
/// (`store_billing.verify_product` raises for iOS), so a pack bought here
/// would be paid for and never granted. Selling something we cannot deliver
/// is both a bad experience and an automatic App Review rejection, so the
/// packs stay hidden on iOS until the verification path ships. Gating lives
/// here, at the one chokepoint every caller goes through, rather than at the
/// five call sites.
Future<void> showTopUpSheet(BuildContext context, {int needed = 0}) =>
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppColors.surface,
      builder: (_) =>
          Platform.isIOS ? const _PacksUnavailable() : _TopUpSheet(needed: needed),
    );

/// What iOS sees in place of the pack grid.
///
/// Deliberately says nothing about buying credits anywhere else. Pointing an
/// iOS customer at a website to buy digital goods is exactly what guideline
/// 3.1.1 forbids, and this app has no reason to go near that line.
class _PacksUnavailable extends ConsumerWidget {
  const _PacksUnavailable();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(appStateProvider);
    final credits = state.credits;
    final isCreator = state.isCreator;
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '⚡ Credits',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 10),
            Text(
              'You have $credits credits. Credit top-ups are coming to iOS '
              'soon.',
              style: const TextStyle(color: AppColors.muted, height: 1.5),
            ),
            const SizedBox(height: 14),
            Text(
              isCreator
                  ? 'Your Creator plan adds 150 credits every month, and only '
                        'successful videos charge — failures are refunded.'
                  : 'Creator adds 150 credits every month on top of 1080p, '
                        '30-second videos and no watermark.',
              style: const TextStyle(color: AppColors.muted, height: 1.5),
            ),
            const SizedBox(height: 18),
            GhostButton(
              label: 'Close',
              height: 46,
              onPressed: () => Navigator.of(context).pop(),
            ),
          ],
        ),
      ),
    );
  }
}

class _TopUpSheet extends ConsumerStatefulWidget {
  const _TopUpSheet({required this.needed});
  final int needed;

  @override
  ConsumerState<_TopUpSheet> createState() => _TopUpSheetState();
}

class _TopUpSheetState extends ConsumerState<_TopUpSheet> {
  CreditPacks? _result;
  String _error = '';

  @override
  void initState() {
    super.initState();
    ref.read(purchaseControllerProvider.notifier).clearPackResult();
    Future.microtask(_load);
  }

  Future<void> _load() async {
    try {
      final result = await ref.read(apiClientProvider).creditPacks();
      if (!mounted) return;
      setState(() => _result = result);
      // Ask the store what each pack costs here.
      await ref
          .read(purchaseControllerProvider.notifier)
          .loadPacks(result.packs);
    } on ApiException catch (error) {
      if (mounted) {
        setState(() {
          _result = const CreditPacks(available: false, packs: []);
          _error = error.message;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final credits = ref.watch(appStateProvider).credits;
    final purchase = ref.watch(purchaseControllerProvider);
    final controller = ref.read(purchaseControllerProvider.notifier);

    if (purchase.packGranted > 0) {
      return _Granted(credits: purchase.packGranted, balance: credits);
    }

    final busy = purchase.packBusy.isNotEmpty;
    final storeError = purchase.packError;

    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '⚡ Top up credits',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 10),
            Text(
              widget.needed > credits
                  ? 'This video needs ${widget.needed} credits — you have $credits. Top-up credits never expire.'
                  : 'You have $credits credits. Top-up credits never expire and work on every plan.',
              style: const TextStyle(color: AppColors.muted, height: 1.5),
            ),
            const SizedBox(height: 18),
            if (_result == null)
              const Column(
                children: [
                  Skeleton(height: 90),
                  SizedBox(height: 10),
                  Skeleton(height: 90),
                ],
              )
            else if (_result!.packs.isEmpty)
              const Text(
                'Credit packs are not available right now.',
                style: TextStyle(color: AppColors.muted),
              )
            else
              GridView.count(
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisCount: 2,
                childAspectRatio: 1.25,
                mainAxisSpacing: 12,
                crossAxisSpacing: 12,
                children: [
                  for (final pack in _result!.packs)
                    _PackTile(
                      pack: pack,
                      storePrice:
                          purchase.packProducts[pack.androidProductId]?.price,
                      busy: purchase.packBusy == pack.androidProductId,
                      enabled:
                          !busy &&
                          purchase.packProducts.containsKey(
                            pack.androidProductId,
                          ),
                      onTap: () => controller.buyPack(pack),
                    ),
                ],
              ),
            if (_error.isNotEmpty || storeError.isNotEmpty) ...[
              const SizedBox(height: 12),
              Notice.error(_error.isNotEmpty ? _error : storeError),
            ],
            const SizedBox(height: 16),
            Text(
              'Secure payment by ${purchase.packProducts.isEmpty ? 'the store' : storeName}. '
              'Credits land in your wallet as soon as the purchase is confirmed. '
              'Only successful videos charge — failures are refunded.',
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 11.5,
                height: 1.5,
                color: AppColors.muted2,
              ),
            ),
            const SizedBox(height: 10),
            TextAction(
              label: 'Close',
              color: AppColors.muted,
              onPressed: busy ? null : () => Navigator.pop(context),
            ),
          ],
        ),
      ),
    );
  }
}

class _PackTile extends StatelessWidget {
  const _PackTile({
    required this.pack,
    required this.storePrice,
    required this.busy,
    required this.enabled,
    required this.onTap,
  });

  final CreditPack pack;
  final String? storePrice;
  final bool busy;
  final bool enabled;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) => AppPanel(
    onTap: enabled ? onTap : null,
    color: pack.popular ? AppColors.cyanWash(0.06) : AppColors.panel,
    borderColor: pack.popular ? AppColors.cyan : AppColors.border,
    padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 12),
    child: Opacity(
      opacity: enabled || busy ? 1 : 0.55,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          if (pack.popular)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
              decoration: BoxDecoration(
                color: AppColors.cyanWash(0.14),
                borderRadius: BorderRadius.circular(AppTheme.radiusPill),
              ),
              child: const Text(
                'POPULAR',
                style: TextStyle(
                  fontSize: 9,
                  color: AppColors.cyan,
                  fontWeight: FontWeight.w800,
                  letterSpacing: 0.5,
                ),
              ),
            )
          else
            const SizedBox(height: 18),
          const SizedBox(height: 4),
          if (busy)
            const InlineSpinner(size: 22)
          else
            Text(
              '${pack.credits}',
              style: const TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w800,
                color: AppColors.text,
              ),
            ),
          Text(
            'credits · ${pack.label}',
            style: const TextStyle(fontSize: 11, color: AppColors.muted),
          ),
          const SizedBox(height: 4),
          Text(
            // The store's price is what gets charged; the USD list price is
            // only a stand-in until the store has answered.
            storePrice ?? '\$${pack.usd.toStringAsFixed(0)}',
            style: const TextStyle(
              color: AppColors.cyan,
              fontWeight: FontWeight.w700,
            ),
          ),
        ],
      ),
    ),
  );
}

class _Granted extends ConsumerWidget {
  const _Granted({required this.credits, required this.balance});

  final int credits;
  final int balance;

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
              child: Text('⚡', style: TextStyle(fontSize: 26)),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            '+$credits credits added',
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          const SizedBox(height: 10),
          Text(
            'You now have $balance credits. They never expire.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodyMedium,
          ),
          const SizedBox(height: 22),
          GradButton(
            label: 'Continue',
            onPressed: () {
              ref.read(purchaseControllerProvider.notifier).clearPackResult();
              Navigator.of(context).pop();
            },
          ),
        ],
      ),
    ),
  );
}
