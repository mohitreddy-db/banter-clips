import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Where the BanterClips session JWT lives.
///
/// The web app keeps it in `localStorage` under `banterclips-session`. The
/// mobile equivalent is NOT `shared_preferences` — that is plaintext on disk
/// and readable on a rooted device. A 30-day session token belongs in the
/// iOS Keychain and the Android Keystore, which is what this wraps.
///
/// The token is read on every request through the Dio interceptor, so it is
/// cached in memory after the first read: a Keychain round-trip per HTTP call
/// is measurable, and the value only changes when we change it.
class TokenStore {
  TokenStore([FlutterSecureStorage? storage])
    : _storage =
          storage ??
          const FlutterSecureStorage(
            aOptions: AndroidOptions(encryptedSharedPreferences: true),
            iOptions: IOSOptions(
              accessibility: KeychainAccessibility.first_unlock,
            ),
          );

  static const _key = 'banterclips-session';

  final FlutterSecureStorage _storage;
  String? _cached;
  bool _loaded = false;

  /// The current session token, or null when signed out.
  Future<String?> read() async {
    if (_loaded) return _cached;
    try {
      _cached = await _storage.read(key: _key);
    } on Exception {
      // A corrupt keystore entry (it happens after some OS restores) must
      // not brick the app — treat it as signed out and let the user back in.
      _cached = null;
    }
    _loaded = true;
    return _cached;
  }

  Future<void> write(String token) async {
    _cached = token;
    _loaded = true;
    await _storage.write(key: _key, value: token);
  }

  Future<void> clear() async {
    _cached = null;
    _loaded = true;
    await _storage.delete(key: _key);
  }

  /// Synchronous peek for the router's redirect, which cannot await. Only
  /// meaningful after [read] has run once — `main()` does that before the
  /// first frame, so by the time any route resolves this is populated.
  String? get cachedToken => _cached;
  bool get hasToken => (_cached ?? '').isNotEmpty;
}
