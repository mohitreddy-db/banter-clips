import 'package:flutter/material.dart';

import 'colors.dart';

/// Type scale for the app surfaces.
///
/// The web app sets `font-family: "Inter", system-ui` on its app screens.
/// Here the family is deliberately left null, which resolves to the
/// platform's own UI font — SF Pro on iOS, Roboto on Android. That is the
/// right default on a phone: it matches system font-size settings, ships no
/// extra bytes, and renders text the OS has already hinted.
///
/// To match the web exactly instead, drop the Inter .ttf files into
/// `assets/fonts/`, declare them under `flutter: fonts:` in pubspec.yaml,
/// and set [fontFamily] to 'Inter'. Everything below picks it up.
class AppType {
  const AppType._();

  static const String? fontFamily = null;

  /// Sizes are the web's, in logical pixels — Figma px map 1:1, so a 15px
  /// label in the design is 15 here with no conversion.
  static const TextTheme textTheme = TextTheme(
    // Screen headline — "What's your sports take?"
    displaySmall: TextStyle(
      fontSize: 30,
      fontWeight: FontWeight.w800,
      height: 1.2,
      color: AppColors.text,
    ),
    // Card / section headline
    headlineSmall: TextStyle(
      fontSize: 21,
      fontWeight: FontWeight.w700,
      height: 1.25,
      color: AppColors.text,
    ),
    titleLarge: TextStyle(
      fontSize: 19,
      fontWeight: FontWeight.w700,
      height: 1.3,
      color: AppColors.text,
    ),
    titleMedium: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.w600,
      height: 1.35,
      color: AppColors.text,
    ),
    titleSmall: TextStyle(
      fontSize: 14,
      fontWeight: FontWeight.w600,
      height: 1.35,
      color: AppColors.text,
    ),
    bodyLarge: TextStyle(
      fontSize: 16,
      fontWeight: FontWeight.w500,
      height: 1.45,
      color: AppColors.text,
    ),
    bodyMedium: TextStyle(
      fontSize: 14,
      fontWeight: FontWeight.w400,
      height: 1.5,
      color: AppColors.muted,
    ),
    bodySmall: TextStyle(
      fontSize: 12.5,
      fontWeight: FontWeight.w400,
      height: 1.5,
      color: AppColors.muted,
    ),
    labelLarge: TextStyle(
      fontSize: 15,
      fontWeight: FontWeight.w600,
      color: AppColors.text,
    ),
    labelMedium: TextStyle(
      fontSize: 13,
      fontWeight: FontWeight.w600,
      color: AppColors.muted,
    ),
    labelSmall: TextStyle(
      fontSize: 11,
      fontWeight: FontWeight.w500,
      color: AppColors.muted2,
    ),
  );

  /// The all-caps section label the app uses everywhere — "SPORT", "TONE",
  /// "PLAN & ALLOWANCE". Letter-spaced, muted, small.
  static const sectionLabel = TextStyle(
    fontSize: 11.5,
    fontWeight: FontWeight.w700,
    letterSpacing: 1.2,
    color: AppColors.muted,
  );

  /// The smaller, dimmer variant used inside script cards.
  static const microLabel = TextStyle(
    fontSize: 10.5,
    fontWeight: FontWeight.w700,
    letterSpacing: 0.8,
    color: AppColors.muted2,
  );
}
