import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:gal/gal.dart';

import '../../api/errors.dart';
import '../../models/clip.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../account/upgrade_sheet.dart';

/// Download a finished clip into the phone's gallery.
///
/// Creator only, and the server is the gate: Free gets a 403
/// `upgrade_required` from `/clips/{id}/download`, which opens the paywall
/// instead of an error. The file the server sends is the watermark-free
/// render (Free renders carry the watermark — that is handled server-side,
/// see BR-08). Nothing is decided here.
///
/// Returns true once the video is in the gallery.
Future<bool> downloadClipToGallery(
  BuildContext context,
  WidgetRef ref,
  Clip clip,
) async {
  final messenger = ScaffoldMessenger.maybeOf(context);
  try {
    final file = await ref.read(apiClientProvider).downloadClip(clip);
    // Android 10+ and iOS need no permission to *add* to the gallery, but
    // older Android does; ask only when the platform says so.
    if (!await Gal.hasAccess()) {
      final granted = await Gal.requestAccess();
      if (!granted) {
        messenger?.showSnackBar(
          const SnackBar(
            content: Text('Allow gallery access to save the video.'),
          ),
        );
        return false;
      }
    }
    await Gal.putVideo(file.path, album: 'BanterClips');
    ref.read(apiClientProvider).track('video_downloaded', {'clip_id': clip.id});
    messenger?.showSnackBar(
      const SnackBar(
        content: Text('Saved to your gallery — BanterClips album.'),
        backgroundColor: AppColors.surface,
      ),
    );
    return true;
  } on ApiException catch (e) {
    if (!context.mounted) return false;
    if (e.needsUpgrade || e.status == 403) {
      showUpgradeSheet(context, reason: UpgradeReason.download);
    } else {
      messenger?.showSnackBar(SnackBar(content: Text(e.message)));
    }
    return false;
  } on GalException catch (e) {
    messenger?.showSnackBar(
      SnackBar(
        content: Text(switch (e.type) {
          GalExceptionType.accessDenied =>
            'Allow gallery access to save the video.',
          GalExceptionType.notEnoughSpace =>
            'Not enough space on this phone to save the video.',
          _ => "The video couldn't be saved to your gallery. Try again.",
        }),
      ),
    );
    return false;
  } catch (_) {
    messenger?.showSnackBar(
      const SnackBar(
        content: Text("The video couldn't be saved. Try again."),
      ),
    );
    return false;
  }
}
