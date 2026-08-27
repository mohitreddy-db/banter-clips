import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'colors.dart';
import 'typography.dart';

/// Assembles the palette and the type scale into the one [ThemeData] the app
/// runs on. Screens read from `Theme.of(context)` rather than importing
/// colours directly wherever a Material widget already exposes the hook.
///
/// The app is dark-only on purpose: the design has one mode, and a
/// half-finished light theme reads worse than none. `themeMode` is pinned to
/// dark in `app.dart` so a phone set to light does not wash it out.
class AppTheme {
  const AppTheme._();

  /// Corner radii, named once. The web uses 20 for cards, 12–14 for panels
  /// and buttons, 999 for pills.
  static const radiusCard = 20.0;
  static const radiusPanel = 12.0;
  static const radiusButton = 14.0;
  static const radiusChip = 10.0;
  static const radiusPill = 999.0;

  /// The gutter every screen body sits inside.
  static const screenPadding = EdgeInsets.symmetric(horizontal: 16);

  static ThemeData get dark {
    const scheme = ColorScheme.dark(
      primary: AppColors.cyan,
      onPrimary: AppColors.onGradient,
      secondary: AppColors.green,
      onSecondary: AppColors.onGradient,
      surface: AppColors.surface,
      onSurface: AppColors.text,
      error: AppColors.error,
      onError: AppColors.text,
      outline: AppColors.border,
    );

    return ThemeData(
      useMaterial3: true,
      brightness: Brightness.dark,
      colorScheme: scheme,
      scaffoldBackgroundColor: AppColors.bg,
      canvasColor: AppColors.bg,
      fontFamily: AppType.fontFamily,
      textTheme: AppType.textTheme,
      splashFactory: InkSparkle.splashFactory,

      appBarTheme: const AppBarTheme(
        backgroundColor: AppColors.bg,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
        foregroundColor: AppColors.text,
        titleTextStyle: TextStyle(
          fontSize: 17,
          fontWeight: FontWeight.w700,
          color: AppColors.text,
        ),
        systemOverlayStyle: SystemUiOverlayStyle(
          statusBarColor: Colors.transparent,
          statusBarIconBrightness: Brightness.light,
          statusBarBrightness: Brightness.dark,
        ),
      ),

      // Input fields: the web's `--app-surface` box with a `--app-border`
      // hairline that turns cyan on focus.
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: AppColors.surface,
        hintStyle: const TextStyle(color: AppColors.muted2, fontWeight: FontWeight.w400),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        border: _inputBorder(AppColors.border),
        enabledBorder: _inputBorder(AppColors.border),
        focusedBorder: _inputBorder(AppColors.cyan, width: 1.5),
        errorBorder: _inputBorder(AppColors.error),
        focusedErrorBorder: _inputBorder(AppColors.error, width: 1.5),
      ),

      dividerTheme: const DividerThemeData(color: AppColors.border, thickness: 1, space: 1),

      bottomSheetTheme: const BottomSheetThemeData(
        backgroundColor: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        showDragHandle: true,
        dragHandleColor: AppColors.muted2,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(radiusCard)),
        ),
      ),

      dialogTheme: const DialogThemeData(
        backgroundColor: AppColors.surface,
        surfaceTintColor: Colors.transparent,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.all(Radius.circular(radiusCard)),
        ),
      ),

      snackBarTheme: const SnackBarThemeData(
        backgroundColor: AppColors.surface,
        contentTextStyle: TextStyle(color: AppColors.text, fontSize: 14),
        behavior: SnackBarBehavior.floating,
      ),

      progressIndicatorTheme: const ProgressIndicatorThemeData(
        color: AppColors.cyan,
        linearTrackColor: AppColors.panel,
        circularTrackColor: Colors.transparent,
      ),

      // Pull-to-refresh in the clips library.
      splashColor: AppColors.cyanWash(0.06),
      highlightColor: AppColors.cyanWash(0.04),
    );
  }

  static OutlineInputBorder _inputBorder(Color color, {double width = 1}) =>
      OutlineInputBorder(
        borderRadius: BorderRadius.circular(radiusPanel),
        borderSide: BorderSide(color: color, width: width),
      );
}
