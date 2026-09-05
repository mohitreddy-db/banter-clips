import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../api/errors.dart';
import '../../state/app_state.dart';

const _creatorProductId = 'creator_monthly';

enum PurchasePhase {
  idle,
  loading,
  buying,
  verifying,
  success,
  failed,
  unavailable,
}

class PurchaseState {
  const PurchaseState({
    this.phase = PurchasePhase.idle,
    this.error = '',
    this.product,
  });

  final PurchasePhase phase;
  final String error;
  final ProductDetails? product;

  bool get busy =>
      phase == PurchasePhase.loading ||
      phase == PurchasePhase.buying ||
      phase == PurchasePhase.verifying;

  // The store supplies a localized price including its currency and taxes.
  String get priceLabel => product?.price ?? '—';

  PurchaseState copyWith({
    PurchasePhase? phase,
    String? error,
    ProductDetails? product,
  }) => PurchaseState(
    phase: phase ?? this.phase,
    error: error ?? this.error,
    product: product ?? this.product,
  );
}

final purchaseControllerProvider =
    NotifierProvider<PurchaseController, PurchaseState>(PurchaseController.new);

class PurchaseController extends Notifier<PurchaseState> {
  final _store = InAppPurchase.instance;
  StreamSubscription<List<PurchaseDetails>>? _purchaseSubscription;

  @override
  PurchaseState build() {
    _purchaseSubscription = _store.purchaseStream.listen(
      _handlePurchases,
      onError: (_) => state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'Google Play could not update the purchase. Please try again.',
      ),
    );
    ref.onDispose(() => _purchaseSubscription?.cancel());
    return const PurchaseState();
  }

  Future<void> loadProduct() async {
    if (state.busy) return;
    state = state.copyWith(phase: PurchasePhase.loading, error: '');
    try {
      if (!await _store.isAvailable()) {
        state = state.copyWith(
          phase: PurchasePhase.unavailable,
          error: 'Google Play Billing is not available on this device.',
        );
        return;
      }

      final response = await _store.queryProductDetails({_creatorProductId});
      if (response.error != null || response.productDetails.isEmpty) {
        state = state.copyWith(
          phase: PurchasePhase.unavailable,
          error: response.error?.message ??
              'The Creator subscription is not available from Google Play yet.',
        );
        return;
      }
      state = PurchaseState(
        phase: PurchasePhase.idle,
        product: response.productDetails.first,
      );
    } catch (_) {
      state = state.copyWith(
        phase: PurchasePhase.unavailable,
        error: 'Could not connect to Google Play. Please try again.',
      );
    }
  }

  Future<void> buy() async {
    if (state.busy) return;
    if (state.product == null) {
      await loadProduct();
      if (state.product == null) return;
    }

    state = state.copyWith(phase: PurchasePhase.buying, error: '');
    try {
      final started = await _store.buyNonConsumable(
        purchaseParam: PurchaseParam(productDetails: state.product!),
      );
      if (!started) {
        state = state.copyWith(
          phase: PurchasePhase.failed,
          error: 'Google Play could not start the purchase.',
        );
      }
    } catch (_) {
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'Google Play could not start the purchase. Please try again.',
      );
    }
  }

  Future<void> restore() async {
    if (state.busy) return;
    state = state.copyWith(phase: PurchasePhase.verifying, error: '');
    try {
      await _store.restorePurchases();
      Future<void>.delayed(const Duration(seconds: 8), () {
        if (state.phase == PurchasePhase.verifying) {
          state = state.copyWith(
            phase: PurchasePhase.failed,
            error: 'No active Creator subscription was found for this Google account.',
          );
        }
      });
    } catch (_) {
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'Google Play could not restore purchases. Please try again.',
      );
    }
  }

  Future<void> _handlePurchases(List<PurchaseDetails> purchases) async {
    final matching = purchases.where((p) => p.productID == _creatorProductId);
    if (matching.isEmpty) return;

    for (final purchase in matching) {
      if (purchase.status == PurchaseStatus.pending) {
        state = state.copyWith(phase: PurchasePhase.buying, error: '');
        continue;
      }
      if (purchase.status == PurchaseStatus.canceled) {
        state = state.copyWith(phase: PurchasePhase.idle, error: '');
        continue;
      }
      if (purchase.status == PurchaseStatus.error) {
        state = state.copyWith(
          phase: PurchasePhase.failed,
          error: purchase.error?.message ?? 'Google Play could not complete the purchase.',
        );
        continue;
      }
      if (purchase.status != PurchaseStatus.purchased &&
          purchase.status != PurchaseStatus.restored) {
        continue;
      }

      state = state.copyWith(phase: PurchasePhase.verifying, error: '');
      try {
        final token = purchase.verificationData.serverVerificationData;
        if (token.isEmpty) {
          throw const ApiException(
            502,
            null,
            'Google Play returned an empty purchase token.',
          );
        }
        await ref.read(apiClientProvider).verifyStorePurchase(
          platform: 'android',
          productId: purchase.productID,
          purchaseToken: token,
          transactionId: purchase.purchaseID,
        );
        if (purchase.pendingCompletePurchase) {
          await _store.completePurchase(purchase);
        }
        await ref.read(appStateProvider.notifier).refreshUser();
        state = state.copyWith(phase: PurchasePhase.success, error: '');
      } on ApiException catch (error) {
        // Do not acknowledge a purchase the server could not verify. Google
        // will redeliver it, allowing a temporary backend outage to recover.
        state = state.copyWith(
          phase: error.status == 503
              ? PurchasePhase.unavailable
              : PurchasePhase.failed,
          error: error.message,
        );
      } catch (_) {
        state = state.copyWith(
          phase: PurchasePhase.failed,
          error: 'Your purchase is pending verification. Reopen the app shortly.',
        );
      }
    }
  }

  void reset() => state = PurchaseState(product: state.product);
}
