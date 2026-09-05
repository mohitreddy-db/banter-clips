import 'package:dio/dio.dart';

/// The Dart counterpart of `ApiError` in `frontend/src/lib/api.js`.
///
/// The backend answers failures as `{"detail": {"code": ..., "message": ...}}`
/// — and sometimes as `{"detail": "a plain string"}`. Unwrapping that in one
/// place is what lets the UI switch on [code] and say "you've used all 5
/// videos this month" instead of "Request failed (402)".
class ApiException implements Exception {
  const ApiException(this.status, this.code, this.message);

  /// HTTP status. 0 means the request never reached the server.
  final int status;

  /// The machine-readable code the backend attaches to the failures the UI
  /// has to react to. See [ApiCode].
  final String? code;

  /// Already human-readable — safe to put straight on screen.
  final String message;

  /// The monthly allowance is spent, or the feature needs Creator. Both open
  /// the same upgrade path, so both are worth asking about together.
  bool get needsUpgrade =>
      code == ApiCode.limitReached || code == ApiCode.upgradeRequired;

  /// The session is gone. The router bounces to sign-in on this.
  bool get isUnauthorized => status == 401;

  /// The phone could not reach the API at all — offline, or the backend is
  /// down. Worth wording differently from a server-side failure.
  bool get isOffline => status == 0;

  @override
  String toString() => 'ApiException($status, $code): $message';

  /// Translate anything Dio throws into our own shape. Called from the
  /// client's single error interceptor, so no screen ever sees a DioException.
  factory ApiException.fromDio(DioException e) {
    switch (e.type) {
      case DioExceptionType.connectionError:
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiException(
          0,
          ApiCode.network,
          "Can't reach BanterClips. Check your connection and try again.",
        );
      case DioExceptionType.cancel:
        return const ApiException(0, ApiCode.cancelled, 'Request cancelled.');
      default:
        break;
    }

    final response = e.response;
    final status = response?.statusCode ?? 0;
    final data = response?.data;

    String? code;
    String? message;
    if (data is Map) {
      final detail = data['detail'];
      if (detail is Map) {
        code = detail['code']?.toString();
        message = detail['message']?.toString();
      } else if (detail != null) {
        message = detail.toString();
      }
      message ??= data['message']?.toString();
    }

    return ApiException(status, code, message ?? _defaultMessage(status));
  }

  static String _defaultMessage(int status) {
    if (status == 0) return "Can't reach BanterClips. Check your connection.";
    if (status == 401) {
      return 'Your session has expired — please sign in again.';
    }
    if (status == 404) return "That isn't there any more.";
    if (status >= 500) {
      return 'BanterClips is having a moment. Try again shortly.';
    }
    return 'Request failed ($status)';
  }
}

/// Every `detail.code` the backend sends that the UI reacts to, plus the two
/// client-side ones. Kept as constants so a typo is a compile error rather
/// than a gate that silently never fires.
class ApiCode {
  const ApiCode._();

  /// 402 — the monthly allowance is spent (BR-09).
  static const limitReached = 'limit_reached';

  /// 403 — Creator-only: download, 1080p, or a clip over 15 seconds.
  static const upgradeRequired = 'upgrade_required';

  /// 503 — the Meta app isn't configured, so fall back to the mock connector.
  static const oauthNotConfigured = 'oauth_not_configured';

  /// Client-side only.
  static const network = 'network';
  static const cancelled = 'cancelled';
}
