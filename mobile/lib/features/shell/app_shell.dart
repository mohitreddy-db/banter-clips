import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../state/app_state.dart';
import '../../theme/colors.dart';

/// The signed-in chrome — the mobile answer to `AppShell.jsx`.
///
/// The web puts navigation in a sidebar (and collapses it to a bottom strip
/// under 860px). A phone only ever gets the bottom strip: thumbs live at the
/// bottom of the screen, and three destinations is exactly what a tab bar is
/// for.
///
/// It wraps a `StatefulShellRoute`, so each tab keeps its own navigation
/// stack and scroll position — switching to Clips and back does not throw
/// away a half-written take.
class AppShell extends ConsumerWidget {
  const AppShell({super.key, required this.navigationShell});

  final StatefulNavigationShell navigationShell;

  /// The web's bottom nav, in its order. Pricing is not a tab there either;
  /// it opens from Account and from every locked control.
  static const _tabs = [
    (
      icon: Icons.add_circle_outline_rounded,
      active: Icons.add_circle_rounded,
      label: 'Create',
    ),
    (
      icon: Icons.local_fire_department_outlined,
      active: Icons.local_fire_department_rounded,
      label: 'Viral',
    ),
    (
      icon: Icons.auto_awesome_outlined,
      active: Icons.auto_awesome_rounded,
      label: 'Prompts',
    ),
    (
      icon: Icons.video_library_outlined,
      active: Icons.video_library_rounded,
      label: 'My Clips',
    ),
    (
      icon: Icons.chat_bubble_outline_rounded,
      active: Icons.chat_bubble_rounded,
      label: 'Feedback',
    ),
    (
      icon: Icons.person_outline_rounded,
      active: Icons.person_rounded,
      label: 'Account',
    ),
  ];

  /// The branch index of My Clips — the one that earns the "rendering" dot.
  static const _clipsTab = 3;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // A clip rendering in the background earns a dot on the Clips tab, so the
    // user knows something is happening without sitting on that screen.
    final busy = ref.watch(appStateProvider.select((s) => s.hasLiveWork));

    return Scaffold(
      body: navigationShell,
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppColors.sidebar,
          border: Border(top: BorderSide(color: AppColors.border)),
        ),
        child: SafeArea(
          top: false,
          child: SizedBox(
            height: 60,
            child: Row(
              children: [
                for (var i = 0; i < _tabs.length; i++)
                  Expanded(
                    child: _Tab(
                      tab: _tabs[i],
                      selected: navigationShell.currentIndex == i,
                      showDot: i == _clipsTab && busy,
                      // `initialLocation: true` when re-tapping the current
                      // tab pops it back to its root — the behaviour every
                      // phone user expects from a tab bar.
                      onTap: () => navigationShell.goBranch(
                        i,
                        initialLocation: i == navigationShell.currentIndex,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Tab extends StatelessWidget {
  const _Tab({
    required this.tab,
    required this.selected,
    required this.onTap,
    this.showDot = false,
  });

  final ({IconData icon, IconData active, String label}) tab;
  final bool selected;
  final VoidCallback onTap;
  final bool showDot;

  @override
  Widget build(BuildContext context) => InkWell(
    onTap: onTap,
    child: Column(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Stack(
          clipBehavior: Clip.none,
          children: [
            Icon(
              selected ? tab.active : tab.icon,
              size: 22,
              color: selected ? AppColors.cyan : AppColors.muted,
            ),
            if (showDot)
              Positioned(
                right: -2,
                top: -1,
                child: Container(
                  width: 8,
                  height: 8,
                  decoration: const BoxDecoration(
                    color: AppColors.cyan,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
          ],
        ),
        const SizedBox(height: 3),
        Text(
          tab.label,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w600,
            color: selected ? AppColors.cyan : AppColors.muted,
          ),
        ),
      ],
    ),
  );
}
