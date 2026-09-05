import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'app/app.dart';
import 'app/env.dart';
import 'theme/colors.dart';

/// Entry point.
///
/// Run against a local backend with:
///
///   flutter run \
///     --dart-define=API_URL=http://10.0.2.2:8000 \
///     --dart-define=SUPABASE_URL=... \
///     --dart-define=SUPABASE_ANON_KEY=...
///
/// With no defines the app talks to production. See `lib/app/env.dart`.
Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Portrait only. Every screen is a vertical column and the product itself
  // is 9:16 — a landscape layout would be a second design to maintain for
  // an orientation nobody holds a phone in to watch a Reel.
  await SystemChrome.setPreferredOrientations([
    DeviceOrientation.portraitUp,
    DeviceOrientation.portraitDown,
  ]);

  // Draw behind the status and navigation bars; the theme paints the dark
  // background under them.
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.light,
      statusBarBrightness: Brightness.dark,
      systemNavigationBarColor: AppColors.sidebar,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  // Supabase is optional at compile time: with no keys the app falls back to
  // the backend's dev magic-link, which is how it runs fully offline.
  if (Env.supabaseEnabled) {
    await Supabase.initialize(
      url: Env.supabaseUrl,
      // The web app and this one share one Supabase project, and that project
      // still issues a legacy anon key. Both clients must send the same key,
      // so this moves to `publishableKey` when the web app does — not before.
      publishableKey: Env.supabaseAnonKey,
      authOptions: const FlutterAuthClientOptions(
        // The Supabase session is only ever traded for our own backend JWT,
        // but it still has to survive a restart so a magic-link return works.
        authFlowType: AuthFlowType.pkce,
      ),
    );
  }

  runApp(const ProviderScope(child: BanterClipsApp()));
}
