import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../theme/colors.dart';
import '../theme/typography.dart';

/// Containers and labels — the `.card`, `.panel` and section-label patterns
/// the whole app is built out of.

/// The main container: `--app-surface` on a hairline border, radius 20.
class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.onTap,
    this.borderColor,
    this.clip = Clip.none,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final VoidCallback? onTap;

  /// Overridden when a card carries state — a highlighted row, an error.
  final Color? borderColor;
  final Clip clip;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(AppTheme.radiusCard),
        border: Border.all(color: borderColor ?? AppColors.border),
      ),
      clipBehavior: clip,
      child: child,
    );
    if (onTap == null) return content;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(AppTheme.radiusCard),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusCard),
        child: content,
      ),
    );
  }
}

/// The inset variant: darker than the card it sits inside, radius 12. Used
/// for stat rows, quoted takes, and every shot in the script view.
class AppPanel extends StatelessWidget {
  const AppPanel({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
    this.color,
    this.borderColor,
    this.onTap,
  });

  final Widget child;
  final EdgeInsetsGeometry padding;
  final Color? color;
  final Color? borderColor;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final content = Container(
      padding: padding,
      decoration: BoxDecoration(
        color: color ?? AppColors.panel,
        borderRadius: BorderRadius.circular(AppTheme.radiusPanel),
        border: Border.all(color: borderColor ?? AppColors.border),
      ),
      child: child,
    );
    if (onTap == null) return content;
    return Material(
      color: Colors.transparent,
      borderRadius: BorderRadius.circular(AppTheme.radiusPanel),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusPanel),
        child: content,
      ),
    );
  }
}

/// "SPORT", "TONE", "PLAN & ALLOWANCE" — the all-caps label above a group,
/// optionally with an action on the right.
class SectionLabel extends StatelessWidget {
  const SectionLabel(this.text, {super.key, this.trailing});

  final String text;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) => Row(
        children: [
          Text(text.toUpperCase(), style: AppType.sectionLabel),
          if (trailing != null) ...[const Spacer(), trailing!],
        ],
      );
}

/// A tinted advisory strip: the cyan info note, the green success note, the
/// red failure note. One widget so their padding and radius cannot drift.
class Notice extends StatelessWidget {
  const Notice({
    super.key,
    required this.text,
    this.tone = NoticeTone.info,
    this.icon,
    this.action,
  });

  const Notice.error(String message, {Key? key})
      : this(key: key, text: message, tone: NoticeTone.error);

  const Notice.success(String message, {Key? key})
      : this(key: key, text: message, tone: NoticeTone.success);

  final String text;
  final NoticeTone tone;
  final IconData? icon;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    final color = switch (tone) {
      NoticeTone.info => AppColors.cyan,
      NoticeTone.success => AppColors.green,
      NoticeTone.error => AppColors.error,
    };
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(AppTheme.radiusPanel),
        border: Border.all(color: color.withValues(alpha: 0.30)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (icon != null) ...[
            Icon(icon, size: 18, color: color),
            const SizedBox(width: 10),
          ],
          Expanded(
            child: Text(
              text,
              style: TextStyle(
                fontSize: 13.5,
                height: 1.45,
                color: tone == NoticeTone.info ? AppColors.muted : color,
                fontWeight: tone == NoticeTone.info ? FontWeight.w400 : FontWeight.w600,
              ),
            ),
          ),
          if (action != null) ...[const SizedBox(width: 8), action!],
        ],
      ),
    );
  }
}

enum NoticeTone { info, success, error }

/// The header every screen body opens with.
class ScreenHeader extends StatelessWidget {
  const ScreenHeader({super.key, required this.title, this.subtitle, this.badge});

  final String title;
  final String? subtitle;

  /// The small pill above the headline — "⚡ NEW CLIP".
  final String? badge;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          if (badge != null) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
              decoration: BoxDecoration(
                color: AppColors.cyanWash(0.10),
                borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                border: Border.all(color: AppColors.cyan.withValues(alpha: 0.35)),
              ),
              child: Text(
                badge!,
                style: const TextStyle(
                  fontSize: 11.5,
                  fontWeight: FontWeight.w700,
                  letterSpacing: 0.9,
                  color: AppColors.cyan,
                ),
              ),
            ),
            const SizedBox(height: 16),
          ],
          Text(
            title,
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.displaySmall,
          ),
          if (subtitle != null) ...[
            const SizedBox(height: 8),
            Text(
              subtitle!,
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium,
            ),
          ],
        ],
      );
}
