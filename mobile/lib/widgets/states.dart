import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../theme/colors.dart';

/// The four states every async screen has: loading, empty, error, content.
///
/// The web version has all four already — these are the mobile equivalents,
/// kept in one file so no screen invents a fifth. The rule the app follows:
/// never leave a screen blank while loading. A skeleton reads as fast; a
/// bare spinner reads as broken.

/// A shimmering placeholder block, sized like the thing it stands in for.
/// This is the `.shimmer` class from `index.css`, as an animation.
class Skeleton extends StatefulWidget {
  const Skeleton({
    super.key,
    this.height = 74,
    this.width = double.infinity,
    this.radius = AppTheme.radiusPanel,
  });

  final double height;
  final double width;
  final double radius;

  @override
  State<Skeleton> createState() => _SkeletonState();
}

class _SkeletonState extends State<Skeleton> with SingleTickerProviderStateMixin {
  late final AnimationController _controller = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1150),
  )..repeat();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _controller,
        builder: (context, _) {
          // Sweep a cyan highlight from left to right across the block.
          final position = _controller.value * 2 - 1;
          return Container(
            height: widget.height,
            width: widget.width,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(widget.radius),
              border: Border.all(color: AppColors.border),
              gradient: LinearGradient(
                begin: Alignment(position - 1, 0),
                end: Alignment(position + 1, 0),
                colors: [
                  Colors.white.withValues(alpha: 0.03),
                  AppColors.cyan.withValues(alpha: 0.14),
                  Colors.white.withValues(alpha: 0.03),
                ],
                stops: const [0.0, 0.45, 1.0],
              ),
            ),
          );
        },
      );
}

/// "No clips yet" — an icon, a headline, a sentence saying what to do next.
class EmptyState extends StatelessWidget {
  const EmptyState({
    super.key,
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final String icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 60),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(icon, style: const TextStyle(fontSize: 40)),
              const SizedBox(height: 14),
              Text(title, style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 8),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              if (action != null) ...[const SizedBox(height: 22), action!],
            ],
          ),
        ),
      );
}

/// The failure state, with the retry the user needs to get out of it.
class ErrorState extends StatelessWidget {
  const ErrorState({super.key, required this.message, this.onRetry});

  final String message;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) => Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 60),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off_rounded, size: 38, color: AppColors.muted2),
              const SizedBox(height: 14),
              Text(
                message,
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              if (onRetry != null) ...[
                const SizedBox(height: 18),
                TextButton(onPressed: onRetry, child: const Text('Try again')),
              ],
            ],
          ),
        ),
      );
}

/// The boot splash, shown while the stored session is checked. Deliberately
/// quiet — it is on screen for a few hundred milliseconds.
class BootSplash extends StatelessWidget {
  const BootSplash({super.key});

  @override
  Widget build(BuildContext context) => const Scaffold(
        backgroundColor: AppColors.bg,
        body: Center(
          child: SizedBox(
            width: 30,
            height: 30,
            child: CircularProgressIndicator(strokeWidth: 2.6, color: AppColors.cyan),
          ),
        ),
      );
}

/// A small inline spinner, sized to sit next to text.
class InlineSpinner extends StatelessWidget {
  const InlineSpinner({super.key, this.size = 16, this.color = AppColors.cyan});

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) => SizedBox(
        width: size,
        height: size,
        child: CircularProgressIndicator(strokeWidth: size / 7.5, color: color),
      );
}
