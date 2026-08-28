import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../api/errors.dart';
import '../../state/app_state.dart';

/// Store billing for the Creator plan.
///
/// Creator is a digital subscription consumed inside the app, so Apple
/// (Guideline 3.1.1) and Google both require it to go through their billing
/// rather than Stripe. This is the client half of that.
///
/// ## The rule that matters
///
/// **The client never decides that someone is a Creator.** A completed
/// purchase is only ever a signal to ask the server; the server verifies the
/// receipt with Apple or Google and is the only thing that writes
/// `users.plan`. Trusting `PurchaseStatus.purchased` on its own is the
/// classic way an app gets a paid tier unlocked with a patched binary.
///
/// So the flow is:
///   1. buy → the store's own sheet
///   2. the purchase stream delivers a receipt
///   3. POST it to `/billing/mobile/verify`
///   4. the server verifies it, flips the plan, and we refetch `/me`
///   5. `completePurchase` — and only then, or the store will refund it
///
/// Step 5 is not optional: an unacknowledged Android purchase is
/// automatically refunded after three days.
enum PurchasePhase { idle, loading, buying, verifying, success, failed, unavailable }

/// The product id, which must match what is created in App Store Connect and
/// the Play Console. Same string on both stores keeps the server simple.
const kCreatorProductId = 'creator_monthly';

class PurchaseState {
  const PurchaseState({
    this.phase = PurchasePhase.idle,
    this.product,
    this.error = '',
  });

  final PurchasePhase phase;

  /// Comes from the store, so the price is right in the user's currency and
  /// region. Never hardcode "$9.99" next to a store product — they diverge.
  final ProductDetails? product;
  final String error;

  bool get busy =>
      phase == PurchasePhase.buying ||
      phase == PurchasePhase.verifying ||
      phase == PurchasePhase.loading;

  /// What the button says. Falls back to the list price only when the store
  /// has not answered yet.
  String get priceLabel => product?.price ?? '\$9.99';

  PurchaseState copyWith({PurchasePhase? phase, ProductDetails? product, String? error}) =>
      PurchaseState(
        phase: phase ?? this.phase,
        product: product ?? this.product,
        error: error ?? this.error,
      );
}

final purchaseControllerProvider =
    NotifierProvider<PurchaseController, PurchaseState>(PurchaseController.new);

class PurchaseController extends Notifier<PurchaseState> {
  StreamSubscription<List<PurchaseDetails>>? _subscription;

  InAppPurchase get _iap => InAppPurchase.instance;

  @override
  PurchaseState build() {
    // The purchase stream must be listened to for the whole life of the app,
    // not just while the paywall is open: a purchase interrupted by a crash,
    // or one that needed the store's "ask to buy" approval, is delivered on
    // the next launch and would otherwise be lost (and auto-refunded).
    _subscription = _iap.purchaseStream.listen(
      _onPurchases,
      onDone: () => _subscription?.cancel(),
      onError: (Object e) => state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'The store connection dropped. Try again.',
      ),
    );
    ref.onDispose(() => _subscription?.cancel());
    return const PurchaseState();
  }

  /// Ask the store what Creator costs here. Call when the paywall opens.
  Future<void> loadProduct() async {
    if (state.product != null || state.phase == PurchasePhase.loading) return;
    state = state.copyWith(phase: PurchasePhase.loading, error: '');

    if (!await _iap.isAvailable()) {
      // A device with no Play Services, or a store account signed out. Say so
      // plainly instead of showing a buy button that cannot work.
      state = state.copyWith(
        phase: PurchasePhase.unavailable,
        error: 'The app store is unavailable on this device right now.',
      );
      return;
    }

    final response = await _iap.queryProductDetails({kCreatorProductId});
    final product = response.productDetails
        .where((p) => p.id == kCreatorProductId)
        .cast<ProductDetails?>()
        .firstWhere((_) => true, orElse: () => null);

    if (product == null) {
      // Almost always a configuration problem, not a user problem: the
      // product is missing, not approved yet, or the build is not signed with
      // a key the store recognises.
      state = state.copyWith(
        phase: PurchasePhase.unavailable,
        error: 'Creator is not available from the store on this build yet.',
      );
      return;
    }
    state = state.copyWith(phase: PurchasePhase.idle, product: product);
  }

  /// Open the store's purchase sheet. Everything after this arrives on the
  /// purchase stream — including a purchase the user completes minutes later
  /// after a "ask to buy" approval.
  Future<void> buy() async {
    final product = state.product;
    if (product == null || state.busy) return;
    state = state.copyWith(phase: PurchasePhase.buying, error: '');
    ref.read(apiClientProvider).track('upgrade_started', {'provider': 'store'});
    try {
      await _iap.buyNonConsumable(
        purchaseParam: PurchaseParam(productDetails: product),
      );
    } catch (e) {
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'The store could not start the purchase. Try again.',
      );
    }
  }

  /// Re-deliver a subscription this device has already paid for — after a
  /// reinstall, or on a second device. Both stores require a visible restore
  /// path; Apple rejects builds without one.
  Future<void> restore() async {
    state = state.copyWith(phase: PurchasePhase.verifying, error: '');
    try {
      await _iap.restorePurchases();
      // Anything found arrives on the stream and is verified like a new buy.
      // If nothing arrives, the phase is reset by the timeout below.
      Future.delayed(const Duration(seconds: 6), () {
        if (state.phase == PurchasePhase.verifying) {
          state = state.copyWith(
            phase: PurchasePhase.idle,
            error: 'No previous Creator purchase was found on this account.',
          );
        }
      });
    } catch (e) {
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'Restore failed. Try again in a moment.',
      );
    }
  }

  Future<void> _onPurchases(List<PurchaseDetails> purchases) async {
    for (final purchase in purchases) {
      switch (purchase.status) {
        case PurchaseStatus.pending:
          state = state.copyWith(phase: PurchasePhase.buying, error: '');

        case PurchaseStatus.canceled:
          // A deliberate choice, not an error. No message.
          state = state.copyWith(phase: PurchasePhase.idle, error: '');

        case PurchaseStatus.error:
          state = state.copyWith(
            phase: PurchasePhase.failed,
            error: purchase.error?.message ?? 'The purchase did not go through.',
          );

        case PurchaseStatus.purchased:
        case PurchaseStatus.restored:
          await _verify(purchase);
      }

      // Always complete, whatever happened. On Android an unacknowledged
      // purchase is refunded after three days; on iOS the transaction is
      // replayed on every launch until it is finished.
      if (purchase.pendingCompletePurchase) {
        await _iap.completePurchase(purchase);
      }
    }
  }

  /// Hand the receipt to our server, which is the only thing that may decide
  /// this account is on Creator.
  Future<void> _verify(PurchaseDetails purchase) async {
    state = state.copyWith(phase: PurchasePhase.verifying, error: '');
    try {
      await ref.read(apiClientProvider).verifyStorePurchase(
            platform: Platform.isIOS ? 'ios' : 'android',
            productId: purchase.productID,
            purchaseToken: purchase.verificationData.serverVerificationData,
            transactionId: purchase.purchaseID,
          );
      // Refetch rather than assuming: /me/usage is the authority on what this
      // account may now do, and it is what every gate in the UI reads.
      await ref.read(appStateProvider.notifier).refreshUser();
      state = state.copyWith(phase: PurchasePhase.success, error: '');
    } on ApiException catch (e) {
      // The money may well have been taken. Never imply it was not — tell
      // them it will be applied and how to force a re-check.
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: e.isOffline
            ? 'Purchase complete, but we could not reach BanterClips to '
                'activate it. Reopen the app on a connection and it will apply.'
            : e.message,
      );
    }
  }

  /// Back to a clean paywall after a failure, keeping the loaded product.
  void reset() => state = state.copyWith(phase: PurchasePhase.idle, error: '');
}
