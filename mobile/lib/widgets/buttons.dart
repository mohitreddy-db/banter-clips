import 'package:flutter/material.dart';

import '../theme/app_theme.dart';
import '../theme/colors.dart';

/// The three button styles the design uses, as three widgets.
///
/// These are the `.grad-btn`, `.ghost-btn` and `.chip` classes from
/// `frontend/src/index.css`, including their disabled and pressed states.
/// Screens never restyle a button inline — if a new variant is needed it
/// belongs here, so the catalog stays the whole truth.

/// The primary action. One per screen, carrying the gradient.
class GradButton extends StatelessWidget {
  const GradButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.loading = false,
    this.expand = true,
    this.height = 52,
    this.fontSize = 16,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;

  /// Shows a spinner and blocks taps. Distinct from `onPressed: null`, which
  /// means "not available" rather than "working on it".
  final bool loading;
  final bool expand;
  final double height;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !loading;
    final child = Container(
      height: height,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        gradient: enabled ? AppColors.gradient : null,
        color: enabled ? null : AppColors.disabledFill,
        borderRadius: BorderRadius.circular(AppTheme.radiusButton),
      ),
      child: loading
          ? const SizedBox(
              width: 20,
              height: 20,
              child: CircularProgressIndicator(
                strokeWidth: 2.4,
                color: AppColors.onGradient,
              ),
            )
          : Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (icon != null) ...[
                  Icon(
                    icon,
                    size: fontSize + 3,
                    color: enabled ? AppColors.onGradient : AppColors.muted2,
                  ),
                  const SizedBox(width: 8),
                ],
                Flexible(
                  child: Text(
                    label,
                    overflow: TextOverflow.ellipsis,
                    style: TextStyle(
                      fontSize: fontSize,
                      fontWeight: FontWeight.w700,
                      color: enabled ? AppColors.onGradient : AppColors.muted2,
                    ),
                  ),
                ),
              ],
            ),
    );

    return SizedBox(
      width: expand ? double.infinity : null,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(AppTheme.radiusButton),
        child: InkWell(
          onTap: enabled ? onPressed : null,
          borderRadius: BorderRadius.circular(AppTheme.radiusButton),
          child: child,
        ),
      ),
    );
  }
}

/// The secondary action: an outlined button that borrows the accent on tap.
class GhostButton extends StatelessWidget {
  const GhostButton({
    super.key,
    required this.label,
    this.onPressed,
    this.icon,
    this.loading = false,
    this.expand = true,
    this.height = 50,
    this.fontSize = 15,
    this.color = AppColors.text,
    this.dashed = false,
    this.trailing,
  });

  final String label;
  final VoidCallback? onPressed;
  final IconData? icon;
  final bool loading;
  final bool expand;
  final double height;
  final double fontSize;
  final Color color;

  /// A dashed border marks "visible but locked" — the upgrade prompt the web
  /// uses for the Download button on Free (BR-08).
  final bool dashed;

  /// Usually the CREATOR pill on a locked action.
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null && !loading;
    return SizedBox(
      width: expand ? double.infinity : null,
      child: Material(
        color: Colors.transparent,
        borderRadius: BorderRadius.circular(AppTheme.radiusButton),
        child: InkWell(
          onTap: enabled ? onPressed : null,
          borderRadius: BorderRadius.circular(AppTheme.radiusButton),
          child: Container(
            height: height,
            alignment: Alignment.center,
            padding: const EdgeInsets.symmetric(horizontal: 16),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(AppTheme.radiusButton),
              border: dashed
                  ? null
                  : Border.all(
                      color: enabled ? AppColors.border : AppColors.border,
                      width: 1,
                    ),
            ),
            foregroundDecoration: dashed
                ? _DashedBorder(
                    radius: AppTheme.radiusButton,
                    color: AppColors.border,
                  )
                : null,
            child: loading
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2.2,
                      color: AppColors.cyan,
                    ),
                  )
                : Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      if (icon != null) ...[
                        Icon(
                          icon,
                          size: fontSize + 3,
                          color: enabled ? color : AppColors.muted2,
                        ),
                        const SizedBox(width: 8),
                      ],
                      Flexible(
                        child: Text(
                          label,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(
                            fontSize: fontSize,
                            fontWeight: FontWeight.w600,
                            color: enabled ? color : AppColors.muted2,
                          ),
                        ),
                      ),
                      if (trailing != null) ...[
                        const SizedBox(width: 8),
                        trailing!,
                      ],
                    ],
                  ),
          ),
        ),
      ),
    );
  }
}

/// A selectable pill — sport, tone, length and quality all use it.
class AppChip extends StatelessWidget {
  const AppChip({
    super.key,
    required this.label,
    required this.selected,
    this.onTap,
    this.locked = false,
    this.trailing,
  });

  final String label;
  final bool selected;
  final VoidCallback? onTap;

  /// Locked chips are still tappable — tapping one opens the upgrade sheet,
  /// which is the whole point of showing it (BR-08).
  final bool locked;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    final borderColor = selected
        ? AppColors.cyan
        : locked
        ? AppColors.muted2
        : AppColors.border;
    return Material(
      color: selected ? AppColors.chipOn : AppColors.chipOff,
      borderRadius: BorderRadius.circular(AppTheme.radiusChip),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(AppTheme.radiusChip),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 11),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(AppTheme.radiusChip),
            border: Border.all(color: borderColor, width: 1),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                label,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
                  color: selected
                      ? AppColors.text
                      : locked
                      ? AppColors.muted2
                      : AppColors.muted,
                ),
              ),
              if (trailing != null) ...[const SizedBox(width: 7), trailing!],
            ],
          ),
        ),
      ),
    );
  }
}

/// The tiny CREATOR badge that marks a locked control.
class CreatorPill extends StatelessWidget {
  const CreatorPill({super.key});

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
    decoration: BoxDecoration(
      color: AppColors.cyanWash(0.12),
      borderRadius: BorderRadius.circular(AppTheme.radiusPill),
    ),
    child: const Text(
      'CREATOR',
      style: TextStyle(
        fontSize: 8,
        fontWeight: FontWeight.w800,
        letterSpacing: 0.5,
        color: AppColors.cyan,
      ),
    ),
  );
}

/// A borderless text action — "Maybe later", "View all →".
class TextAction extends StatelessWidget {
  const TextAction({
    super.key,
    required this.label,
    this.onPressed,
    this.color = AppColors.cyan,
    this.fontSize = 13.5,
  });

  final String label;
  final VoidCallback? onPressed;
  final Color color;
  final double fontSize;

  @override
  Widget build(BuildContext context) => TextButton(
    onPressed: onPressed,
    style: TextButton.styleFrom(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      minimumSize: Size.zero,
      tapTargetSize: MaterialTapTargetSize.shrinkWrap,
      foregroundColor: color,
    ),
    child: Text(
      label,
      style: TextStyle(
        fontSize: fontSize,
        fontWeight: FontWeight.w600,
        color: color,
      ),
    ),
  );
}

/// Flutter has no dashed border, and the locked-download affordance needs
/// one to read as "not a real button yet".
class _DashedBorder extends Decoration {
  const _DashedBorder({required this.radius, required this.color});

  final double radius;
  final Color color;

  @override
  BoxPainter createBoxPainter([VoidCallback? onChanged]) =>
      _DashedBorderPainter(radius: radius, color: color);
}

class _DashedBorderPainter extends BoxPainter {
  _DashedBorderPainter({required this.radius, required this.color});

  final double radius;
  final Color color;

  @override
  void paint(Canvas canvas, Offset offset, ImageConfiguration configuration) {
    final size = configuration.size ?? Size.zero;
    final rect = offset & size;
    final rrect = RRect.fromRectAndRadius(
      rect.deflate(0.5),
      Radius.circular(radius),
    );
    final paint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;

    // Walk the rounded rectangle and draw 5px on, 4px off.
    for (final metric in (Path()..addRRect(rrect)).computeMetrics()) {
      var distance = 0.0;
      while (distance < metric.length) {
        final next = (distance + 5).clamp(0.0, metric.length);
        canvas.drawPath(metric.extractPath(distance, next), paint);
        distance = next + 4;
      }
    }
  }
}
