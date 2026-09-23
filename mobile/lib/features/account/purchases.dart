import 'dart:async';
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:in_app_purchase/in_app_purchase.dart';

import '../../api/client.dart';
import '../../api/errors.dart';
import '../../state/app_state.dart';

/// The Creator subscription, as created in the Play Console / App Store
/// Connect. Same id in both stores so the server verifies without caring
/// where the receipt came from.
const creatorProductId = 'creator_monthly';

/// The plan price everywhere it is written down: pricing page, account,
/// PRICING.md. The store bills in local currency at the price configured in
/// its console; that figure is shown alongside so the customer sees both.
const creatorPriceLabel = r'$19';

/// The store that actually takes the money on this platform, for copy shown
/// to the customer. iOS reviewers reject a paywall that names Google Play.
String get storeName => Platform.isIOS ? 'the App Store' : 'Google Play';

/// Where an existing subscription is managed, in the customer's words.
String get storeSubscriptionsName =>
    Platform.isIOS ? 'App Store subscriptions' : 'Play Store subscriptions';

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
    this.packProducts = const {},
    this.packBusy = '',
    this.packError = '',
    this.packGranted = 0,
  });

  final PurchasePhase phase;
  final String error;

  /// The Creator subscription, once the store has described it.
  final ProductDetails? product;

  /// Credit packs the store knows about, keyed by product id.
  final Map<String, ProductDetails> packProducts;

  /// The product id of the pack currently being bought or verified.
  final String packBusy;
  final String packError;

  /// Credits the last pack purchase added, once the server confirmed it.
  final int packGranted;

  bool get busy =>
      phase == PurchasePhase.loading ||
      phase == PurchasePhase.buying ||
      phase == PurchasePhase.verifying;

  /// What the store will actually bill, in the customer's currency and
  /// with their taxes — "₹1,599.00", "$18.99". Null until loaded.
  String? get storePrice => product?.price;

  PurchaseState copyWith({
    PurchasePhase? phase,
    String? error,
    ProductDetails? product,
    Map<String, ProductDetails>? packProducts,
    String? packBusy,
    String? packError,
    int? packGranted,
  }) => PurchaseState(
    phase: phase ?? this.phase,
    error: error ?? this.error,
    product: product ?? this.product,
    packProducts: packProducts ?? this.packProducts,
    packBusy: packBusy ?? this.packBusy,
    packError: packError ?? this.packError,
    packGranted: packGranted ?? this.packGranted,
  );
}

final purchaseControllerProvider =
    NotifierProvider<PurchaseController, PurchaseState>(PurchaseController.new);

/// Everything that talks to Google Play Billing / StoreKit.
///
/// One rule, repeated from the README: **the client never decides who is a
/// Creator or how many credits they have.** A completed purchase is only a
/// signal to go and ask the server, which verifies the receipt with the
/// store and is the only thing allowed to change `users.plan` or the wallet.
class PurchaseController extends Notifier<PurchaseState> {
  final _store = InAppPurchase.instance;
  StreamSubscription<List<PurchaseDetails>>? _purchaseSubscription;
  Timer? _buyTimeout;

  /// The pack product ids we are expecting purchases for, so a receipt can
  /// be told apart from the subscription's.
  final Set<String> _knownPackIds = {};

  String get _platform => Platform.isIOS ? 'ios' : 'android';

  /// The signed-in BanterClips user id, handed to the store when a purchase
  /// starts. The store carries it through and gives it back to the server as
  /// Apple's `appAccountToken` / Play's `obfuscatedAccountId`, and the server
  /// refuses any receipt whose token does not match the account redeeming it.
  /// A purchase started without one verifies fine and is then rejected with
  /// `purchase_account_mismatch` — paid for, never granted — so every buy
  /// path must set it.
  String? get _accountToken => ref.read(appStateProvider).user?.id;
  String get _storeName => storeName;

  @override
  PurchaseState build() {
    _purchaseSubscription = _store.purchaseStream.listen(
      _handlePurchases,
      onError: (_) => state = state.copyWith(
        phase: PurchasePhase.failed,
        error: '$_storeName could not update the purchase. Please try again.',
      ),
    );
    ref.onDispose(() {
      _purchaseSubscription?.cancel();
      _buyTimeout?.cancel();
    });
    return const PurchaseState();
  }

  // -------------------------------------------------------- subscription

  Future<void> loadProduct() async {
    if (state.busy) return;
    state = state.copyWith(phase: PurchasePhase.loading, error: '');
    try {
      if (!await _store.isAvailable()) {
        state = state.copyWith(
          phase: PurchasePhase.unavailable,
          error: '$_storeName billing is not available on this device.',
        );
        return;
      }

      final response = await _store.queryProductDetails({creatorProductId});
      if (response.error != null || response.productDetails.isEmpty) {
        state = state.copyWith(
          phase: PurchasePhase.unavailable,
          error:
              'The Creator subscription is not available from $_storeName yet.',
        );
        return;
      }
      state = state.copyWith(
        phase: PurchasePhase.idle,
        product: response.productDetails.first,
      );
    } catch (_) {
      state = state.copyWith(
        phase: PurchasePhase.unavailable,
        error: 'Could not connect to $_storeName. Please try again.',
      );
    }
  }

  Future<void> buy() async {
    if (state.busy) return;
    if (state.product == null) {
      await loadProduct();
      if (state.product == null) return;
    }

    final accountToken = _accountToken;
    if (accountToken == null) {
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: 'Sign in again before subscribing.',
      );
      return;
    }

    state = state.copyWith(phase: PurchasePhase.buying, error: '');
    _armBuyTimeout();
    try {
      final started = await _store.buyNonConsumable(
        purchaseParam: PurchaseParam(
          productDetails: state.product!,
          applicationUserName: accountToken,
        ),
      );
      if (!started) {
        _disarmBuyTimeout();
        state = state.copyWith(
          phase: PurchasePhase.failed,
          error: '$_storeName could not start the purchase.',
        );
      }
    } catch (_) {
      _disarmBuyTimeout();
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: '$_storeName could not start the purchase. Please try again.',
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
            error:
                'No active Creator subscription was found for this $_storeName account.',
          );
        }
      });
    } catch (_) {
      state = state.copyWith(
        phase: PurchasePhase.failed,
        error: '$_storeName could not restore purchases. Please try again.',
      );
    }
  }

  /// If the store sheet is dismissed in a way that never reaches the
  /// purchase stream (it happens on some Android builds), the button must
  /// not stay on "loading" forever. Two minutes is longer than any real
  /// checkout; after that the user gets the button back.
  void _armBuyTimeout() {
    _buyTimeout?.cancel();
    _buyTimeout = Timer(const Duration(minutes: 2), () {
      if (state.phase == PurchasePhase.buying) {
        state = state.copyWith(phase: PurchasePhase.idle, error: '');
      }
      if (state.packBusy.isNotEmpty) {
        state = state.copyWith(packBusy: '', packError: '');
      }
    });
  }

  void _disarmBuyTimeout() {
    _buyTimeout?.cancel();
    _buyTimeout = null;
  }

  // ------------------------------------------------------- credit packs

  /// Ask the store to describe the credit packs. Missing ones simply do not
  /// appear as buyable; the sheet says so rather than showing a dead button.
  Future<void> loadPacks(List<CreditPack> packs) async {
    final ids = packs.map((p) => p.androidProductId).toSet();
    _knownPackIds.addAll(ids);
    try {
      if (!await _store.isAvailable()) {
        state = state.copyWith(
          packError: '$_storeName billing is not available on this device.',
        );
        return;
      }
      final response = await _store.queryProductDetails(ids);
      state = state.copyWith(
        packProducts: {for (final d in response.productDetails) d.id: d},
        packError: response.productDetails.isEmpty
            ? 'Credit packs are not on sale in $_storeName yet.'
            : '',
      );
    } catch (_) {
      state = state.copyWith(
        packError: 'Could not connect to $_storeName. Please try again.',
      );
    }
  }

  Future<void> buyPack(CreditPack pack) async {
    if (state.packBusy.isNotEmpty || state.busy) return;
    final details = state.packProducts[pack.androidProductId];
    if (details == null) {
      state = state.copyWith(
        packError: 'That pack is not on sale in $_storeName yet.',
      );
      return;
    }
    final accountToken = _accountToken;
    if (accountToken == null) {
      state = state.copyWith(packError: 'Sign in again before buying credits.');
      return;
    }
    _knownPackIds.add(details.id);
    state = state.copyWith(
      packBusy: details.id,
      packError: '',
      packGranted: 0,
    );
    _armBuyTimeout();
    try {
      // autoConsume is off on purpose: the credits are granted by the
      // server after it verifies the token, and only THEN is the purchase
      // consumed. Consuming first would let a verification failure eat a
      // paid purchase with nothing to show for it.
      final started = await _store.buyConsumable(
        purchaseParam: PurchaseParam(
          productDetails: details,
          applicationUserName: accountToken,
        ),
        autoConsume: false,
      );
      if (!started) {
        _disarmBuyTimeout();
        state = state.copyWith(
          packBusy: '',
          packError: '$_storeName could not start the purchase.',
        );
      }
    } catch (_) {
      _disarmBuyTimeout();
      state = state.copyWith(
        packBusy: '',
        packError:
            '$_storeName could not start the purchase. Please try again.',
      );
    }
  }

  // ------------------------------------------------------------- stream

  Future<void> _handlePurchases(List<PurchaseDetails> purchases) async {
    for (final purchase in purchases) {
      final isPack = _knownPackIds.contains(purchase.productID);
      final isSubscription = purchase.productID == creatorProductId;

      // A cancelled or failed checkout on Android arrives with an EMPTY
      // product id — filtering on the id first is exactly how the button
      // used to stay on "loading" forever after the Play sheet was closed.
      if (purchase.status == PurchaseStatus.canceled) {
        _disarmBuyTimeout();
        state = state.copyWith(
          phase: state.phase == PurchasePhase.buying
              ? PurchasePhase.idle
              : state.phase,
          error: '',
          packBusy: '',
          packError: '',
        );
        continue;
      }
      if (purchase.status == PurchaseStatus.error) {
        _disarmBuyTimeout();
        final message = _friendly(purchase.error?.message);
        if (state.packBusy.isNotEmpty && (isPack || !isSubscription)) {
          state = state.copyWith(packBusy: '', packError: message);
        } else {
          state = state.copyWith(phase: PurchasePhase.failed, error: message);
        }
        continue;
      }
      if (purchase.status == PurchaseStatus.pending) {
        if (isPack) {
          state = state.copyWith(packBusy: purchase.productID, packError: '');
        } else if (isSubscription) {
          state = state.copyWith(phase: PurchasePhase.buying, error: '');
        }
        continue;
      }
      if (purchase.status != PurchaseStatus.purchased &&
          purchase.status != PurchaseStatus.restored) {
        continue;
      }
      if (!isPack && !isSubscription) continue;

      _disarmBuyTimeout();
      if (isPack) {
        await _verifyPack(purchase);
      } else {
        await _verifySubscription(purchase);
      }
    }
  }

  Future<void> _verifySubscription(PurchaseDetails purchase) async {
    state = state.copyWith(phase: PurchasePhase.verifying, error: '');
    try {
      await ref
          .read(apiClientProvider)
          .verifyStorePurchase(
            platform: _platform,
            productId: purchase.productID,
            purchaseToken: _token(purchase),
            transactionId: purchase.purchaseID,
          );
      if (purchase.pendingCompletePurchase) {
        await _store.completePurchase(purchase);
      }
      await ref.read(appStateProvider.notifier).refreshUser();
      state = state.copyWith(phase: PurchasePhase.success, error: '');
    } on ApiException catch (error) {
      // Do not acknowledge a purchase the server could not verify. The store
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

  Future<void> _verifyPack(PurchaseDetails purchase) async {
    state = state.copyWith(packBusy: purchase.productID, packError: '');
    try {
      final result = await ref
          .read(apiClientProvider)
          .verifyStorePurchase(
            platform: _platform,
            productId: purchase.productID,
            purchaseToken: _token(purchase),
            transactionId: purchase.purchaseID,
          );
      // Only now, with the credits in the wallet server-side, is the
      // purchase consumed — which is what lets it be bought again.
      if (purchase.pendingCompletePurchase) {
        await _store.completePurchase(purchase);
      }
      await ref.read(appStateProvider.notifier).refreshUsage();
      state = state.copyWith(
        packBusy: '',
        packError: '',
        packGranted: (result['credits_granted'] as num?)?.toInt() ?? 0,
      );
    } on ApiException catch (error) {
      state = state.copyWith(packBusy: '', packError: error.message);
    } catch (_) {
      state = state.copyWith(
        packBusy: '',
        packError:
            'Your purchase is pending verification. Reopen the app shortly '
            '— the credits will appear once it clears.',
      );
    }
  }

  String _token(PurchaseDetails purchase) {
    final token = purchase.verificationData.serverVerificationData;
    if (token.isEmpty) {
      throw ApiException(
        502,
        null,
        '$_storeName returned an empty purchase token.',
      );
    }
    return token;
  }

  String _friendly(String? raw) {
    final text = (raw ?? '').toLowerCase();
    if (text.contains('cancel')) return '';
    if (text.contains('already owned')) {
      return 'You already own this. Tap "Refresh an existing subscription".';
    }
    if (text.contains('network') || text.contains('unavailable')) {
      return "$_storeName couldn't be reached. Check your connection and try again.";
    }
    return '$_storeName could not complete the purchase. Please try again.';
  }

  void reset() => state = PurchaseState(
    product: state.product,
    packProducts: state.packProducts,
  );

  void clearPackResult() => state = state.copyWith(packGranted: 0, packError: '');
}
