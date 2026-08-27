import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../features/account/account_screen.dart';
import '../features/auth/sign_in_screen.dart';
import '../features/clips/clips_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/shell/app_shell.dart';
import '../features/studio/clip_screen.dart';
import '../features/studio/studio_screen.dart';
import '../state/app_state.dart';

/// Routing and the auth gate — the Dart counterpart of `App.jsx`.
///
/// The web guards routes by wrapping them in `<AppShell>`, which redirects to
/// `/signin`. go_router does the same job in one `redirect` callback, which
/// is better: the rule lives in one place and applies to deep links too.
///
/// Deliberately absent, matching the mobile scope decision:
///   * `/` landing and `/showcase` — marketing and SEO surfaces. Somebody who
///     installed the app has already converted.
///   * `/admin/*` — ops tooling, desktop browser forever.
///   * `/pricing`, `/privacy`, `/terms` — opened as web pages (Account).
final routerProvider = Provider<GoRouter>((ref) {
  // go_router needs a Listenable to know when to re-run `redirect`. Bridging
  // the Riverpod state through one keeps the router itself stateless.
  final refresh = ValueNotifier<int>(0);
  ref.onDispose(refresh.dispose);
  ref.listen(
    appStateProvider,
    (previous, next) {
      // Only nudge the router when something it actually gates on moved.
      if (previous?.signedIn != next.signedIn ||
          previous?.onboarded != next.onboarded ||
          previous?.booted != next.booted) {
        refresh.value++;
      }
    },
  );

  return GoRouter(
    initialLocation: '/studio',
    refreshListenable: refresh,
    redirect: (context, routerState) {
      final app = ref.read(appStateProvider);
      // Boot has not finished. `app.dart` is showing the splash, so hold
      // every route where it is rather than flashing sign-in at a user who
      // turns out to be signed in.
      if (!app.booted) return null;

      final path = routerState.matchedLocation;
      final onAuthRoute = path == '/sign-in';

      if (!app.signedIn) return onAuthRoute ? null : '/sign-in';

      // Signed in but the profile is empty: onboarding first. Reachable
      // again later from Account, hence the explicit allowance below.
      if (!app.onboarded && path != '/onboarding') return '/onboarding';

      if (onAuthRoute) return app.onboarded ? '/studio' : '/onboarding';
      return null;
    },
    routes: [
      GoRoute(
        path: '/sign-in',
        builder: (context, state) => const SignInScreen(),
      ),
      GoRoute(
        path: '/onboarding',
        builder: (context, state) => const OnboardingScreen(),
      ),

      // One clip, full screen: script review, live progress, or the finished
      // player. Pushed on top of the shell so back always means "leave it".
      GoRoute(
        path: '/clip/:id',
        parentNavigatorKey: _rootNavigatorKey,
        builder: (context, state) => ClipScreen(clipId: state.pathParameters['id']!),
      ),

      StatefulShellRoute.indexedStack(
        builder: (context, state, navigationShell) => AppShell(navigationShell: navigationShell),
        branches: [
          StatefulShellBranch(
            routes: [GoRoute(path: '/studio', builder: (context, state) => const StudioScreen())],
          ),
          StatefulShellBranch(
            routes: [GoRoute(path: '/clips', builder: (context, state) => const ClipsScreen())],
          ),
          StatefulShellBranch(
            routes: [GoRoute(path: '/account', builder: (context, state) => const AccountScreen())],
          ),
        ],
      ),
    ],
    navigatorKey: _rootNavigatorKey,
    errorBuilder: (context, state) => Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('🤔', style: TextStyle(fontSize: 34)),
              const SizedBox(height: 12),
              Text(
                "That screen doesn't exist.",
                style: Theme.of(context).textTheme.titleMedium,
              ),
              const SizedBox(height: 16),
              TextButton(
                onPressed: () => context.go('/studio'),
                child: const Text('Back to Create'),
              ),
            ],
          ),
        ),
      ),
    ),
  );
});

final _rootNavigatorKey = GlobalKey<NavigatorState>();
