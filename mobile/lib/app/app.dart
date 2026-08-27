import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../state/app_state.dart';
import '../theme/app_theme.dart';
import '../widgets/states.dart';
import 'router.dart';

/// The root widget.
///
/// Two jobs: hold the boot splash until the stored session has been checked,
/// and hand everything after that to the router. Doing the wait here rather
/// than inside `redirect` is what stops a signed-in user seeing the sign-in
/// screen flash past on every cold start.
class BanterClipsApp extends ConsumerStatefulWidget {
  const BanterClipsApp({super.key});

  @override
  ConsumerState<BanterClipsApp> createState() => _BanterClipsAppState();
}

class _BanterClipsAppState extends ConsumerState<BanterClipsApp> {
  @override
  void initState() {
    super.initState();
    // A sign-in that finishes in the browser (Google, magic link, email
    // confirmation) comes back through this stream.
    ref.read(appStateProvider.notifier).listenToSupabase();
  }

  @override
  Widget build(BuildContext context) {
    final booted = ref.watch(appStateProvider.select((s) => s.booted));

    if (!booted) {
      return MaterialApp(
        debugShowCheckedModeBanner: false,
        theme: AppTheme.dark,
        // Dark-only: the design has one mode, and the phone's own setting
        // must not wash it out.
        themeMode: ThemeMode.dark,
        home: const BootSplash(),
      );
    }

    return MaterialApp.router(
      title: 'BanterClips',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.dark,
      darkTheme: AppTheme.dark,
      themeMode: ThemeMode.dark,
      routerConfig: ref.watch(routerProvider),
      builder: (context, child) {
        // Respect the system font-size setting, but stop a 200% accessibility
        // scale from breaking every layout in the app. 1.3 is the point past
        // which the take box and the stage list stop fitting a small phone.
        final scale = MediaQuery.textScalerOf(context).clamp(maxScaleFactor: 1.3);
        return MediaQuery(
          data: MediaQuery.of(context).copyWith(textScaler: scale),
          child: child!,
        );
      },
    );
  }
}
