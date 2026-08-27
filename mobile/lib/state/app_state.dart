import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart' as sb;

import '../api/client.dart';
import '../api/errors.dart';
import '../api/token_store.dart';
import '../app/env.dart';
import '../models/clip.dart';
import '../models/social.dart';
import '../models/user.dart';

/// The app's shared state — the Dart port of `frontend/src/state/AppContext.jsx`.
///
/// One notifier holds what every screen needs (who is signed in, what they
/// are allowed to do, their clips, their connected accounts) and exposes the
/// same derived gates the web computes. Screens read slices of it with
/// `ref.watch(...)`; nothing recomputes plan rules locally.

final tokenStoreProvider = Provider<TokenStore>((ref) => TokenStore());

final apiClientProvider = Provider<ApiClient>((ref) {
  final client = ApiClient(tokens: ref.watch(tokenStoreProvider));
  // A 401 anywhere signs the app out, which the router notices immediately.
  client.onUnauthorized = () => ref.read(appStateProvider.notifier).handleSessionExpired();
  return client;
});

final appStateProvider =
    NotifierProvider<AppStateNotifier, AppState>(AppStateNotifier.new);

/// Everything the shell and the screens read. Immutable — every change goes
/// through [AppStateNotifier], which is what makes the router's redirect
/// trustworthy.
@immutable
class AppState {
  const AppState({
    this.booted = false,
    this.user,
    this.usage,
    this.clips = const [],
    this.socials = const [],
    this.apiDown = false,
  });

  /// False until the stored session has been checked. The router shows a
  /// splash rather than flashing the sign-in screen at a signed-in user.
  final bool booted;

  final User? user;
  final Usage? usage;
  final List<Clip> clips;
  final List<SocialAccount> socials;

  /// The API could not be reached at boot. Worth saying out loud — the
  /// alternative is an empty app that looks broken.
  final bool apiDown;

  bool get signedIn => user != null;

  // ---- Derived plan gates. Usage is the authority; the user row is the
  // fallback, exactly as the web resolves them. -----------------------------

  String get plan => usage?.plan ?? user?.plan ?? 'free';
  bool get isCreator => plan == 'creator';
  int get limit => usage?.limit ?? (isCreator ? 30 : 5);
  int get used => usage?.used ?? 0;
  int get left => usage?.left ?? (limit - used).clamp(0, limit);

  /// BR-08 / client non-negotiable #1: Free is publish-only.
  bool get canDownload => usage?.canDownload ?? isCreator;
  bool get watermarked => usage?.watermarked ?? !isCreator;

  bool get onboarded => user?.preferences.onboardingCompleted ?? false;

  SocialAccount? get instagram {
    for (final account in socials) {
      if (account.platform == 'instagram') return account;
    }
    return null;
  }

  bool get instagramConnected => instagram?.isConnected ?? false;

  /// True while any clip is rendering or any publish is in flight — the
  /// clips library uses this to decide whether to keep polling.
  bool get hasLiveWork =>
      clips.any((c) => c.inFlight) || clips.any((c) => c.isPublishing);

  AppState copyWith({
    bool? booted,
    User? user,
    Usage? usage,
    List<Clip>? clips,
    List<SocialAccount>? socials,
    bool? apiDown,
    bool clearUser = false,
  }) =>
      AppState(
        booted: booted ?? this.booted,
        user: clearUser ? null : (user ?? this.user),
        usage: clearUser ? null : (usage ?? this.usage),
        clips: clearUser ? const [] : (clips ?? this.clips),
        socials: clearUser ? const [] : (socials ?? this.socials),
        apiDown: apiDown ?? this.apiDown,
      );
}

class AppStateNotifier extends Notifier<AppState> {
  @override
  AppState build() {
    // Boot runs once, off the first frame, so the constructor stays cheap.
    Future.microtask(boot);
    return const AppState();
  }

  ApiClient get _api => ref.read(apiClientProvider);
  TokenStore get _tokens => ref.read(tokenStoreProvider);

  sb.SupabaseClient? get _supabase =>
      Env.supabaseEnabled ? sb.Supabase.instance.client : null;

  // ------------------------------------------------------------------ boot

  /// Restore the session if a token exists, then load everything at once.
  Future<void> boot() async {
    final token = await _tokens.read();
    if (token == null || token.isEmpty) {
      state = state.copyWith(booted: true);
      return;
    }
    try {
      await _loadAll();
      state = state.copyWith(booted: true, apiDown: false);
    } on ApiException catch (e) {
      if (e.isUnauthorized) {
        await _tokens.clear();
        state = const AppState(booted: true);
      } else {
        // Offline or the API is down: keep the token (the session may still
        // be valid) and say so rather than pretending to be signed out.
        state = state.copyWith(booted: true, apiDown: e.isOffline);
      }
    }
  }

  Future<void> _loadAll() async {
    final results = await Future.wait([
      _api.me(),
      _api.usage(),
      _api.listClips(),
      _api.listSocials(),
    ]);
    state = state.copyWith(
      user: results[0] as User,
      usage: results[1] as Usage,
      clips: results[2] as List<Clip>,
      socials: results[3] as List<SocialAccount>,
    );
  }

  // ------------------------------------------------------------------ auth

  /// Trade a Supabase access token for our own session, then load the app.
  Future<User> _exchange(String supabaseAccessToken) async {
    final session = await _api.exchangeSupabase(supabaseAccessToken);
    await _tokens.write(session.accessToken);
    state = state.copyWith(user: session.user);
    await _loadAll();
    return state.user!;
  }

  /// Email + password sign-up. With email confirmation switched on in
  /// Supabase there is no session yet — the caller shows "check your inbox"
  /// rather than assuming it worked.
  Future<bool> signUp({
    required String email,
    required String password,
    String? displayName,
  }) async {
    final supabase = _requireSupabase();
    final res = await supabase.auth.signUp(
      email: email,
      password: password,
      data: {'display_name': displayName?.trim().isNotEmpty == true
          ? displayName!.trim()
          : email.split('@').first},
    );
    final session = res.session;
    if (session == null) return false; // needs email confirmation
    await _exchange(session.accessToken);
    return true;
  }

  Future<void> signInWithPassword({required String email, required String password}) async {
    final supabase = _requireSupabase();
    final res = await supabase.auth.signInWithPassword(email: email, password: password);
    final session = res.session;
    if (session == null) {
      throw const ApiException(401, null, 'Sign-in failed — please try again.');
    }
    await _exchange(session.accessToken);
  }

  /// Google, through Supabase OAuth in a system browser sheet. The session
  /// arrives on the auth stream, which [listenToSupabase] exchanges.
  Future<void> signInWithGoogle() async {
    final supabase = _requireSupabase();
    await supabase.auth.signInWithOAuth(
      sb.OAuthProvider.google,
      redirectTo: '${Env.oauthScheme}://login-callback',
      authScreenLaunchMode: sb.LaunchMode.externalApplication,
      // Always show the account chooser. Without it Google silently reuses
      // the last account, and there is no way to pick another from here.
      queryParams: const {'prompt': 'select_account'},
    );
  }

  Future<void> sendMagicLink(String email) async {
    final supabase = _requireSupabase();
    await supabase.auth.signInWithOtp(
      email: email,
      emailRedirectTo: '${Env.oauthScheme}://login-callback',
    );
  }

  Future<void> sendPasswordReset(String email) async {
    final supabase = _requireSupabase();
    await supabase.auth.resetPasswordForEmail(
      email,
      redirectTo: '${Env.oauthScheme}://reset-password',
    );
  }

  Future<void> updatePassword(String password) async {
    final supabase = _requireSupabase();
    await supabase.auth.updateUser(sb.UserAttributes(password: password));
  }

  /// Dev fallback when Supabase isn't configured. Requires the backend to
  /// run with DEV_MODE=true; anywhere else it 404s.
  Future<void> devSignIn(String email) async {
    final token = await _api.requestDevLink(email);
    if (token == null) {
      throw const ApiException(0, null, 'Check your inbox for the sign-in link.');
    }
    final session = await _api.verifyDevToken(token);
    await _tokens.write(session.accessToken);
    state = state.copyWith(user: session.user);
    await _loadAll();
  }

  /// Subscribes to Supabase auth changes so a sign-in that completes in the
  /// browser (Google, magic link, email confirmation) lands us a session
  /// without the user coming back to tap anything.
  void listenToSupabase() {
    final supabase = _supabase;
    if (supabase == null) return;
    supabase.auth.onAuthStateChange.listen((event) async {
      final session = event.session;
      if (session == null) return;
      if (event.event == sb.AuthChangeEvent.signedIn ||
          event.event == sb.AuthChangeEvent.tokenRefreshed) {
        if (_tokens.hasToken) return; // already exchanged
        try {
          await _exchange(session.accessToken);
        } on ApiException {
          // The backend rejected it (blocked account, or it is down). The
          // sign-in screen stays put and shows its own error.
        }
      }
    });
  }

  /// Called by the API client when anything returns 401.
  void handleSessionExpired() {
    if (!state.signedIn) return;
    state = state.copyWith(clearUser: true, booted: true);
  }

  Future<void> signOut() async {
    await _tokens.clear();
    await _supabase?.auth.signOut();
    state = const AppState(booted: true);
  }

  // -------------------------------------------------------------- refresh

  /// Each refresher keeps the last known value on failure. A transient poll
  /// error must never blank a screen the user is looking at.

  Future<void> refreshUser() async {
    try {
      state = state.copyWith(user: await _api.me());
      await refreshUsage();
    } on ApiException {/* keep what we have */}
  }

  Future<void> refreshUsage() async {
    try {
      state = state.copyWith(usage: await _api.usage());
    } on ApiException {/* keep what we have */}
  }

  Future<void> refreshClips() async {
    try {
      state = state.copyWith(clips: await _api.listClips());
    } on ApiException {/* keep what we have */}
  }

  Future<void> refreshSocials() async {
    try {
      state = state.copyWith(socials: await _api.listSocials());
    } on ApiException {/* keep what we have */}
  }

  /// Merge one freshly-polled clip into the list without a round-trip for
  /// the rest — the studio polls a single clip every couple of seconds.
  void mergeClip(Clip clip) {
    final next = [...state.clips];
    final index = next.indexWhere((c) => c.id == clip.id);
    if (index >= 0) {
      next[index] = clip;
    } else {
      next.insert(0, clip);
    }
    state = state.copyWith(clips: next);
  }

  void removeClip(String id) =>
      state = state.copyWith(clips: state.clips.where((c) => c.id != id).toList());

  // ---------------------------------------------------------- preferences

  Future<void> savePreferences({
    List<String>? sports,
    List<String>? teams,
    List<String>? players,
    String? role,
    bool? onboardingCompleted,
  }) async {
    final saved = await _api.updatePreferences(
      sports: sports,
      teams: teams,
      players: players,
      role: role,
      onboardingCompleted: onboardingCompleted,
    );
    final user = state.user;
    if (user != null) state = state.copyWith(user: user.copyWith(preferences: saved));
  }

  // -------------------------------------------------------------- socials

  Future<void> disconnectInstagram() async {
    await _api.disconnectSocial('instagram');
    await refreshSocials();
  }

  sb.SupabaseClient _requireSupabase() {
    final supabase = _supabase;
    if (supabase == null) {
      throw const ApiException(
        0,
        null,
        'Sign-in is not configured in this build. '
            'Pass --dart-define=SUPABASE_URL and --dart-define=SUPABASE_ANON_KEY.',
      );
    }
    return supabase;
  }
}
