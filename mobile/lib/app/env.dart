/// Compile-time configuration — the Flutter counterpart of `frontend/.env`.
///
/// Vite inlines `VITE_*` at build time; Dart does the same with
/// `--dart-define`, read back through `String.fromEnvironment`. There is no
/// runtime .env file to forget to ship, and no secret here that a browser
/// would not also see (the Supabase anon key is publishable by design).
///
/// Local development against the backend on this machine:
///
///   flutter run \
///     --dart-define=API_URL=http://10.0.2.2:8000 \
///     --dart-define=SUPABASE_URL=https://taphbakizdagamimbhjh.supabase.co \
///     --dart-define=SUPABASE_ANON_KEY=YOUR_ANON_KEY
///
/// 10.0.2.2 — not localhost — is how the Android emulator reaches the host
/// machine. Inside the emulator `localhost` is the emulator itself.
library;

class Env {
  const Env._();

  /// Which API the app talks to. Defaults to production so a plain
  /// `flutter build apk` produces a shippable app.
  static const apiUrl = String.fromEnvironment(
    'API_URL',
    defaultValue: 'https://api.banterclips.com',
  );

  /// Supabase Auth (project "banterclips") — the same project the web app
  /// uses, so an account created on the site signs in here unchanged.
  static const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');

  /// With both empty the app falls back to the backend's dev magic-link
  /// (`/auth/request-link`, which only exists when DEV_MODE=true).
  static bool get supabaseEnabled =>
      supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;

  /// Where the marketing site lives. Pricing, privacy and terms are opened
  /// here rather than rebuilt — both stores require reachable legal links,
  /// and Apple's Guideline 4.2 only objects to webviews that ARE the app.
  static const webUrl = 'https://www.banterclips.com';
  static const privacyUrl = '$webUrl/privacy';
  static const termsUrl = '$webUrl/terms';
  static const pricingUrl = '$webUrl/pricing';

  /// The custom scheme the Instagram consent screen returns to. Registered
  /// in AndroidManifest.xml and Info.plist, and allow-listed server-side.
  static const oauthScheme = 'banterclips';
  static const igRedirect = '$oauthScheme://oauth/instagram';
}
