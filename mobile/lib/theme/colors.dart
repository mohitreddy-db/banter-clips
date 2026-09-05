import 'package:flutter/material.dart';

/// The app palette.
///
/// Every value below is a Figma variable from
/// **BanterClips — Phase 1 MVP** (`ow8js7BjcJumixFMyVgKyH`), verified against
/// the file rather than eyeballed, and cross-checked against the `--app-*`
/// custom properties the web app ships in `frontend/src/index.css`. The
/// Figma name is in the comment, so a token rename there is greppable here.
///
/// One source of truth per colour — nothing below this file hardcodes a hex.
class AppColors {
  const AppColors._();

  static const bg = Color(0xFF0B0F1C); // bg/app
  static const sidebar = Color(0xFF080C16); // bg/sidebar — the bottom nav here
  static const surface = Color(0xFF131A2B); // bg/surface — cards
  static const panel = Color(0xFF0F1524); // bg/panel — inset panels
  static const border = Color(0xFF232C40); // border/subtle
  static const cyan = Color(0xFF22D3EE); // accent/cyan — primary
  static const green = Color(0xFF34E27A); // accent/green — success
  static const text = Color(0xFFF4F6FB); // text/primary
  static const muted = Color(0xFF8B93A7); // text/secondary
  static const muted2 = Color(0xFF4A5468); // status/disabled

  /// Not a published Figma variable — it comes from `--app-error` in the web
  /// stylesheet. Worth promoting to a `status/error` variable in Figma so
  /// failure states stop being defined in two places.
  static const error = Color(0xFFF0546C);

  /// `chip/selected-bg` is a Figma variable; the resting fill is only in the
  /// CSS (`.chip`), so it has the same caveat as [error].
  static const chipOn = Color(0xFF12303D); // chip/selected-bg
  static const chipOff = Color(0xFF161E30);

  /// The disabled fill of `.grad-btn:disabled`.
  static const disabledFill = Color(0xFF1A2234);

  /// Ink on top of the gradient button — near-black with a cyan cast, so the
  /// label reads as part of the gradient rather than pasted onto it.
  static const onGradient = Color(0xFF06121A);

  /// `--app-grad`: the single brand gradient, used for primary buttons and
  /// progress fills. Left to right, exactly as the CSS declares it.
  static const gradient = LinearGradient(
    begin: Alignment.centerLeft,
    end: Alignment.centerRight,
    colors: [cyan, green],
  );

  /// Instagram's brand ramp, for the connected-account avatar.
  static const instagram = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [Color(0xFF7B2FF7), Color(0xFFF0546C)],
  );

  /// Translucent accent washes. The web writes these inline as
  /// `rgba(34,211,238,.08)`; naming them keeps the opacities consistent
  /// instead of drifting a hundredth at a time across screens.
  static Color cyanWash([double opacity = 0.08]) =>
      cyan.withValues(alpha: opacity);
  static Color greenWash([double opacity = 0.10]) =>
      green.withValues(alpha: opacity);
  static Color errorWash([double opacity = 0.10]) =>
      error.withValues(alpha: opacity);

  /// Fallback thumbnail for a clip with no poster frame yet. The backend
  /// sends `thumb_gradient` as a CSS gradient string, which Flutter cannot
  /// parse — so we key a deterministic local gradient off the clip id
  /// instead of trying to translate CSS at runtime.
  static LinearGradient thumbFor(String seed) {
    const ramps = [
      [Color(0xFF22D3EE), Color(0xFF3D2C8D)],
      [Color(0xFF34E27A), Color(0xFF0F5132)],
      [Color(0xFF7B2FF7), Color(0xFFF0546C)],
      [Color(0xFFF97316), Color(0xFF7C2D12)],
      [Color(0xFF22D3EE), Color(0xFF0B4A6F)],
    ];
    final ramp = ramps[seed.hashCode.abs() % ramps.length];
    return LinearGradient(
      begin: Alignment.topLeft,
      end: Alignment.bottomRight,
      colors: ramp,
    );
  }
}
