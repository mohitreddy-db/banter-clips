import 'dart:io';

import 'package:dio/dio.dart';
import 'package:path_provider/path_provider.dart';

import '../app/env.dart';
import '../models/clip.dart';
import '../models/social.dart';
import '../models/user.dart';
import 'errors.dart';
import 'token_store.dart';

/// The BanterClips API, method for method from `frontend/src/lib/api.js`.
///
/// That file is the specification: the two clients talk to the same FastAPI
/// server, so anything that drifts here is a bug in one of them. The
/// authoritative response shapes are at `${Env.apiUrl}/docs`.
///
/// Deliberately NOT ported: everything under `/admin`. Ops tooling belongs on
/// a desktop browser — see the mobile roadmap, phase 03.
class ApiClient {
  ApiClient({required TokenStore tokens, Dio? dio})
    : _tokens = tokens,
      _dio = dio ?? Dio() {
    _dio.options = _dio.options.copyWith(
      baseUrl: Env.apiUrl,
      // Generous, because the API fronts a render pipeline: enhancement and
      // caption writing are model calls that can take a few seconds. Only
      // the *poll* is expected to be fast, and it is a tiny GET.
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 45),
      sendTimeout: const Duration(seconds: 30),
      contentType: Headers.jsonContentType,
      // We read status codes ourselves in the error interceptor, but letting
      // Dio throw for non-2xx keeps every call site free of status checks.
      validateStatus: (status) =>
          status != null && status >= 200 && status < 300,
    );

    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final token = await _tokens.read();
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
        onError: (e, handler) async {
          final error = ApiException.fromDio(e);
          // A 401 from a normal API route means our BanterClips session has
          // expired. A 401 from /auth/* means the *new Supabase credential*
          // was rejected; invalidating the existing BanterClips session in
          // that case used to log people out during an automatic refresh.
          if (error.isUnauthorized &&
              !e.requestOptions.path.startsWith('/auth/')) {
            onUnauthorized?.call();
          }
          handler.reject(
            DioException(
              requestOptions: e.requestOptions,
              error: error,
              response: e.response,
            ),
          );
        },
      ),
    );
  }

  final Dio _dio;
  final TokenStore _tokens;

  /// Called when an authenticated API request comes back 401. The notifier
  /// first tries to renew it from Supabase before deciding to sign out.
  void Function()? onUnauthorized;

  // ------------------------------------------------------------------ core

  Future<dynamic> _send(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
  }) async {
    try {
      final res = await _dio.request<dynamic>(
        path,
        data: body,
        queryParameters: query,
        options: Options(method: method),
      );
      return res.data;
    } on DioException catch (e) {
      // The interceptor already translated it; unwrap and rethrow so callers
      // only ever catch ApiException.
      final error = e.error;
      throw error is ApiException ? error : ApiException.fromDio(e);
    }
  }

  Future<Map<String, dynamic>> _map(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
  }) async {
    final data = await _send(method, path, body: body, query: query);
    return data is Map ? Map<String, dynamic>.from(data) : <String, dynamic>{};
  }

  Future<List<Map<String, dynamic>>> _listOf(
    String method,
    String path, {
    Object? body,
    Map<String, dynamic>? query,
  }) async {
    final data = await _send(method, path, body: body, query: query);
    return data is List
        ? data
              .whereType<Map>()
              .map((e) => Map<String, dynamic>.from(e))
              .toList()
        : <Map<String, dynamic>>[];
  }

  // ------------------------------------------------------------------ auth

  /// Trade a Supabase access token for a 30-day BanterClips session.
  ///
  /// This is the same two-step dance the web does: Supabase authenticates,
  /// the backend verifies that token against Supabase Auth, finds or creates
  /// the user row, and issues its OWN session JWT. Everything after this
  /// carries the backend token — never the Supabase one.
  Future<Session> exchangeSupabase(String accessToken) async {
    final json = await _map(
      'POST',
      '/auth/supabase',
      body: {'access_token': accessToken},
    );
    return Session.fromJson(json);
  }

  /// Dev-only fallback (404s unless the backend runs with DEV_MODE=true).
  Future<String?> requestDevLink(String email, {String? displayName}) async {
    final json = await _map(
      'POST',
      '/auth/request-link',
      body: {
        'email': email,
        if (displayName != null) 'display_name': displayName,
      },
    );
    return json['dev_token'] as String?;
  }

  Future<Session> verifyDevToken(String token) async {
    final json = await _map('POST', '/auth/verify', body: {'token': token});
    return Session.fromJson(json);
  }

  // -------------------------------------------------------------------- me

  Future<User> me() async => User.fromJson(await _map('GET', '/me'));

  Future<Usage> usage() async => Usage.fromJson(await _map('GET', '/me/usage'));

  /// Delete the account and everything in it. Irreversible, and the session
  /// it was called with is dead the moment it returns.
  ///
  /// It does not cancel a store subscription — only Apple or Google can —
  /// which is why the screen that calls this says so first.
  Future<void> deleteAccount() async => _send('DELETE', '/me');

  Future<Preferences> updatePreferences({
    List<String>? sports,
    List<String>? teams,
    List<String>? players,
    String? role,
    bool? onboardingCompleted,
  }) async {
    // Send only what changed: the endpoint is a PATCH with
    // `exclude_unset`, so a null we include would clear the field.
    final body = <String, dynamic>{
      if (sports != null) 'sports': sports,
      if (teams != null) 'teams': teams,
      if (players != null) 'players': players,
      if (role != null) 'role': role,
      if (onboardingCompleted != null)
        'onboarding_completed': onboardingCompleted,
    };
    return Preferences.fromJson(
      await _map('PATCH', '/me/preferences', body: body),
    );
  }

  // ----------------------------------------------------------------- clips

  Future<List<Clip>> listClips() async =>
      (await _listOf('GET', '/clips')).map(Clip.fromJson).toList();

  Future<Clip> getClip(String id) async =>
      Clip.fromJson(await _map('GET', '/clips/$id'));

  /// Starts a render. Throws [ApiException] with `insufficient_credits` when
  /// the wallet cannot cover the quoted price and `upgrade_required` for 30s
  /// or 1080p on Free — both server-enforced, so the client gates are
  /// courtesy, not security.
  ///
  /// The body is exactly what `api.createClip` sends on the web: several
  /// sports (the server works one out from the take when none are given),
  /// the people in it, an optional direction and an uploaded reference key.
  Future<Clip> createClip({
    required String take,
    required String tone,
    List<String> sports = const [],
    List<String> subjects = const [],
    String direction = '',
    String? referenceKey,
    int duration = 15,
    String resolution = '720p',
  }) async {
    final json = await _map(
      'POST',
      '/clips',
      body: {
        'take': take,
        'sports': sports,
        'subjects': subjects,
        'tone': tone,
        'duration': duration,
        'resolution': resolution,
        'direction': direction,
        'reference_key': referenceKey,
      },
    );
    return Clip.fromJson(json);
  }

  /// Uploads a reference photo (JPEG) or video (MP4) and returns the storage
  /// key to pass to [createClip]. The web posts the raw file body with its
  /// content type — not multipart — so this does the same.
  Future<String> uploadReference(
    File file, {
    required String contentType,
  }) async {
    try {
      final length = await file.length();
      final res = await _dio.post<dynamic>(
        '/clips/reference',
        data: file.openRead(),
        options: Options(
          contentType: contentType,
          headers: {Headers.contentLengthHeader: length},
          sendTimeout: const Duration(minutes: 3),
          receiveTimeout: const Duration(minutes: 2),
        ),
      );
      final data = res.data;
      final key = data is Map ? data['key']?.toString() ?? '' : '';
      if (key.isEmpty) {
        throw const ApiException(
          502,
          null,
          'The reference could not be stored.',
        );
      }
      return key;
    } on DioException catch (e) {
      final error = e.error;
      throw error is ApiException ? error : ApiException.fromDio(e);
    }
  }

  /// Two fresh, sharper wordings of a take. Repeatable — [round] only widens
  /// the search, so pressing again gives new ideas rather than rephrasings.
  /// An empty list is a valid answer: it means the take is good as written.
  Future<List<TakeVariation>> enhanceTake({
    required String take,
    String? sport,
    String? tone,
    int round = 0,
  }) async {
    final json = await _map(
      'POST',
      '/clips/enhance-take',
      body: {
        'take': take,
        if (sport != null) 'sport': sport,
        if (tone != null) 'tone': tone,
        'round': round,
      },
    );
    final variations = json['variations'];
    return variations is List
        ? variations
              .whereType<Map>()
              .map((e) => TakeVariation.fromJson(Map<String, dynamic>.from(e)))
              .toList()
        : <TakeVariation>[];
  }

  /// Today's stories for a sport. Cheap — a shared 20-minute server cache
  /// per sport — so calling it on every screen open is fine. [refresh] asks
  /// the server to rebuild the feed from today's internet, which it only
  /// honours once its own cooldown has passed.
  Future<TrendingFeed> trending(String sport, {bool refresh = false}) async =>
      TrendingFeed.fromJson(
        await _map(
          'GET',
          '/clips/trending',
          query: {'sport': sport, if (refresh) 'refresh': '1'},
        ),
      );

  /// Three caption options to pick between when publishing. [avoid] carries
  /// what has already been shown so a "new suggestions" press produces
  /// genuinely new ones rather than a reshuffle.
  Future<List<String>> captionSuggestions(
    String clipId, {
    List<String> avoid = const [],
  }) async {
    final json = await _map(
      'GET',
      '/clips/$clipId/captions',
      query: avoid.isEmpty ? null : {'avoid': avoid.join('\n')},
    );
    final captions = json['captions'];
    return captions is List
        ? captions.map((e) => e.toString()).toList()
        : <String>[];
  }

  /// Retries are free — the allowance is only charged on success (BR-09).
  Future<Clip> retryClip(String id) async =>
      Clip.fromJson(await _map('POST', '/clips/$id/retry'));

  /// Save edited dialogue and actions. [edits] is the sparse patch built by
  /// `Script.diffAgainst` — only the shots that actually changed.
  Future<Clip> updateScript(
    String id,
    List<Map<String, dynamic>> edits,
  ) async => Clip.fromJson(
    await _map('PATCH', '/clips/$id/script', body: {'scenes': edits}),
  );

  /// The money gate: nothing renders, and nothing is spent, until this.
  Future<Clip> approveScript(String id) async =>
      Clip.fromJson(await _map('POST', '/clips/$id/script/approve'));

  /// Throw the script away and write a different one. Free — only the render
  /// costs, and it hasn't started.
  Future<Clip> regenerateScript(String id, {String feedback = ''}) async =>
      Clip.fromJson(
        await _map(
          'POST',
          '/clips/$id/script/regenerate',
          body: {'feedback': feedback},
        ),
      );

  Future<void> deleteClip(String id) async => _send('DELETE', '/clips/$id');

  /// Downloads the MP4 to a temp file and returns it, ready for the share
  /// sheet. Creator only — Free gets 403 `upgrade_required`, which the UI
  /// turns into the upgrade prompt rather than an error.
  Future<File> downloadClip(Clip clip) async {
    final dir = await getTemporaryDirectory();
    final file = File('${dir.path}/${clip.downloadFilename}');
    try {
      await _dio.download('/clips/${clip.id}/download', file.path);
      return file;
    } on DioException catch (e) {
      final error = e.error;
      throw error is ApiException ? error : ApiException.fromDio(e);
    }
  }

  // ------------------------------------------------------------ publishing

  /// Fire-and-forget: the upload runs server-side and the clips library
  /// shows live status. BR-13 — publishing is always an explicit per-clip act.
  ///
  /// [tiktok] and [youtube] carry the per-platform options those APIs
  /// require (privacy level and interaction flags; title, description and
  /// visibility). Instagram needs only the caption.
  Future<Publish> publishClip({
    required String clipId,
    required String socialAccountId,
    required String caption,
    Map<String, dynamic>? tiktok,
    Map<String, dynamic>? youtube,
  }) async {
    final json = await _map(
      'POST',
      '/clips/$clipId/publish',
      body: {
        'social_account_id': socialAccountId,
        'caption': caption,
        if (tiktok != null) 'tiktok': tiktok,
        if (youtube != null) 'youtube': youtube,
      },
    );
    return Publish.fromJson(json);
  }

  /// What TikTok will let this account post right now. Fetched every time
  /// the publish sheet opens on TikTok — the privacy options and disabled
  /// interactions are TikTok's to decide, per post.
  Future<TikTokCreatorInfo> tiktokCreatorInfo() async =>
      TikTokCreatorInfo.fromJson(
        await _map('GET', '/socials/tiktok/creator-info'),
      );

  // -------------------------------------------------------------- feedback

  /// The feedback form. [page] records where in the app it was sent from.
  Future<void> sendFeedback({
    required String message,
    String category = 'other',
    int? rating,
    String page = '',
  }) async => _send(
    'POST',
    '/feedback',
    body: {
      'message': message,
      'category': category,
      'rating': rating,
      'page': page,
    },
  );

  Future<Publish> getPublish(String clipId, String publishId) async =>
      Publish.fromJson(
        await _map('GET', '/clips/$clipId/publishes/$publishId'),
      );

  // --------------------------------------------------------------- socials

  Future<List<SocialAccount>> listSocials() async =>
      (await _listOf('GET', '/socials')).map(SocialAccount.fromJson).toList();

  /// The Meta consent URL. [next] is where the backend sends the browser
  /// afterwards — on mobile that must be our custom scheme, which the
  /// backend allow-lists explicitly (see the deep-link note in README).
  ///
  /// Throws `oauth_not_configured` (503) when the Meta app isn't set up, and
  /// the caller falls back to [connectSocial]'s mock connector.
  Future<String?> socialOauthUrl(
    String platform, {
    String next = Env.igRedirect,
  }) async {
    final json = await _map(
      'GET',
      '/socials/$platform/oauth-url',
      query: {'next': next},
    );
    return json['url'] as String?;
  }

  Future<String?> instagramOauthUrl({String next = Env.igRedirect}) =>
      socialOauthUrl('instagram', next: next);

  /// The mock connector — immediately returns a connected account. Real
  /// OAuth goes through [instagramOauthUrl] first.
  Future<SocialAccount> connectSocial(String platform) async =>
      SocialAccount.fromJson(
        await _map('POST', '/socials/connect', body: {'platform': platform}),
      );

  Future<void> disconnectSocial(String platform) async =>
      _send('DELETE', '/socials/$platform');

  // --------------------------------------------------------------- billing

  /// Hand a store receipt to the server, which verifies it with Apple or
  /// Google and is the only thing that may set `users.plan`.
  ///
  /// Called after every completed or restored purchase. Safe to repeat: the
  /// endpoint is idempotent, keyed on the store's own purchase token, so a
  /// retry after a dropped connection converges rather than double-granting.
  ///
  /// The same endpoint verifies a credit-pack purchase: the server tells the
  /// two apart by product id, grants the credits, and consumes the purchase.
  Future<Map<String, dynamic>> verifyStorePurchase({
    required String platform,
    required String productId,
    required String purchaseToken,
    String? transactionId,
  }) => _map(
    'POST',
    '/billing/mobile/verify',
    body: {
      'platform': platform,
      'product_id': productId,
      'purchase_token': purchaseToken,
      if (transactionId != null) 'transaction_id': transactionId,
    },
  );

  /// Stripe Checkout. Returns null when Stripe isn't configured (503).
  ///
  /// Kept for parity with the web client, but the app must not call it to
  /// sell a subscription: Apple 3.1.1 and Google both require store billing
  /// for digital goods consumed in-app. See `purchases.dart`.
  Future<String?> checkout() async {
    try {
      final json = await _map('POST', '/billing/checkout');
      return json['url'] as String?;
    } on ApiException catch (e) {
      if (e.status == 503) return null;
      rethrow;
    }
  }

  Future<String?> billingPortal() async {
    final json = await _map('POST', '/billing/portal');
    return json['url'] as String?;
  }

  Future<void> cancelPlan() async => _send('POST', '/billing/cancel');

  /// The credit packs on sale. On a phone these are bought through the
  /// store (see `top_up_sheet.dart`); the Stripe URL from [topUpCredits] is
  /// the website's path and must not be used to sell credits in-app.
  Future<CreditPacks> creditPacks() async =>
      CreditPacks.fromJson(await _map('GET', '/billing/packs'));

  Future<String> topUpCredits(String pack) async {
    final json = await _map('POST', '/billing/topup', body: {'pack': pack});
    final url = json['url']?.toString() ?? '';
    if (url.isEmpty) {
      throw const ApiException(502, null, 'Payment checkout is unavailable.');
    }
    return url;
  }

  /// Read-only admin console data. Server-side authorization remains the
  /// source of truth and deliberately returns 404 to non-admin accounts.
  Future<Map<String, dynamic>> adminGet(
    String path, {
    Map<String, dynamic>? query,
  }) => _map('GET', path, query: query);

  // ------------------------------------------------------------- analytics

  /// Fire-and-forget, exactly like the web: analytics must never surface an
  /// error or block anything the user asked for.
  void track(String name, [Map<String, dynamic> props = const {}]) {
    _send(
      'POST',
      '/events',
      body: {'name': name, 'props': props},
    ).catchError((_) => null);
  }
}

class CreditPack {
  const CreditPack({
    required this.key,
    required this.credits,
    required this.usd,
    this.popular = false,
    this.name = '',
    String? androidProductId,
  }) : _androidProductId = androidProductId;
  final String key;
  final String name;
  final int credits;
  final double usd;
  final bool popular;
  final String? _androidProductId;

  /// The Play Console product for this pack. The server may name it; when
  /// it does not, the convention `credits_<pack>` applies, and the server
  /// side of `/billing/mobile/verify` maps it back the same way.
  String get androidProductId => (_androidProductId?.isNotEmpty ?? false)
      ? _androidProductId!
      : 'credits_$key';

  String get label =>
      name.isNotEmpty ? name : key[0].toUpperCase() + key.substring(1);

  factory CreditPack.fromJson(Map<String, dynamic> json) => CreditPack(
    key: json['key']?.toString() ?? '',
    name: json['name']?.toString() ?? '',
    credits: (json['credits'] as num?)?.toInt() ?? 0,
    usd: (json['usd'] as num?)?.toDouble() ?? 0,
    popular: json['popular'] as bool? ?? false,
    androidProductId: json['android_product_id']?.toString(),
  );
}

class CreditPacks {
  const CreditPacks({required this.available, required this.packs});
  final bool available;
  final List<CreditPack> packs;

  factory CreditPacks.fromJson(Map<String, dynamic> json) => CreditPacks(
    available: json['available'] as bool? ?? false,
    packs: (json['packs'] as List? ?? const [])
        .whereType<Map>()
        .map((item) => CreditPack.fromJson(Map<String, dynamic>.from(item)))
        .where((item) => item.key.isNotEmpty)
        .toList(),
  );
}

/// `SessionResponse` — the backend session token plus the user it belongs to.
class Session {
  const Session({required this.accessToken, required this.user});

  final String accessToken;
  final User user;

  factory Session.fromJson(Map<String, dynamic> json) => Session(
    accessToken: json['access_token']?.toString() ?? '',
    user: User.fromJson(Map<String, dynamic>.from(json['user'] as Map)),
  );
}
