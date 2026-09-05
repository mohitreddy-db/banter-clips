import 'package:chewie/chewie.dart';
import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

import '../../theme/colors.dart';
import '../../widgets/states.dart';

/// A 9:16 player for a finished clip.
///
/// Vertical video wants a full-bleed frame, not a letterboxed rectangle
/// inside a 16:9 box — so the aspect ratio is fixed at 9:16 and the video
/// covers it. Going fullscreen switches to `contain`, which is what the web
/// does too (see the `video:fullscreen` rule in `index.css`): cropping a
/// preview is fine, cropping the thing someone is watching is not.
class ClipPlayer extends StatefulWidget {
  const ClipPlayer({
    super.key,
    required this.url,
    this.watermarked = false,
    this.autoPlay = false,
    this.onPlay,
  });

  final String url;

  /// Free clips carry the BanterClips mark. It is burnt into the video
  /// server-side; this overlay just matches what the player shows on the web
  /// so the preview is honest about what will be published.
  final bool watermarked;
  final bool autoPlay;
  final VoidCallback? onPlay;

  @override
  State<ClipPlayer> createState() => _ClipPlayerState();
}

class _ClipPlayerState extends State<ClipPlayer> {
  VideoPlayerController? _video;
  ChewieController? _chewie;
  String _error = '';
  bool _reportedPlay = false;

  @override
  void initState() {
    super.initState();
    _open();
  }

  @override
  void didUpdateWidget(ClipPlayer oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.url != widget.url) {
      _dispose();
      _open();
    }
  }

  Future<void> _open() async {
    final video = VideoPlayerController.networkUrl(Uri.parse(widget.url));
    _video = video;
    try {
      await video.initialize();
      if (!mounted) return;
      video.addListener(_watchForFirstPlay);
      setState(() {
        _chewie = ChewieController(
          videoPlayerController: video,
          autoPlay: widget.autoPlay,
          looping: false,
          allowMuting: true,
          allowPlaybackSpeedChanging: false,
          aspectRatio: 9 / 16,
          materialProgressColors: ChewieProgressColors(
            playedColor: AppColors.cyan,
            handleColor: AppColors.cyan,
            backgroundColor: AppColors.muted2,
            bufferedColor: AppColors.muted,
          ),
        );
      });
    } catch (_) {
      if (mounted) {
        setState(
          () => _error =
              "This video couldn't be loaded. Pull to refresh and try again.",
        );
      }
    }
  }

  /// Fires the analytics event once, the first time playback actually starts
  /// — matching the web's `onPlay` on the `<video>` element.
  void _watchForFirstPlay() {
    if (_reportedPlay) return;
    if (_video?.value.isPlaying ?? false) {
      _reportedPlay = true;
      widget.onPlay?.call();
    }
  }

  void _dispose() {
    _video?.removeListener(_watchForFirstPlay);
    _chewie?.dispose();
    _video?.dispose();
    _chewie = null;
    _video = null;
  }

  @override
  void dispose() {
    _dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AspectRatio(
    aspectRatio: 9 / 16,
    child: ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Container(
        color: Colors.black,
        child: Stack(
          fit: StackFit.expand,
          children: [
            if (_error.isNotEmpty)
              Center(
                child: Padding(
                  padding: const EdgeInsets.all(20),
                  child: Text(
                    _error,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppColors.muted,
                    ),
                  ),
                ),
              )
            else if (_chewie == null)
              const Center(child: InlineSpinner(size: 26))
            else
              Chewie(controller: _chewie!),
            if (widget.watermarked && _error.isEmpty)
              Positioned(
                right: 10,
                bottom: 52,
                child: IgnorePointer(
                  child: Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 8,
                      vertical: 4,
                    ),
                    decoration: BoxDecoration(
                      color: Colors.black.withValues(alpha: 0.55),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: const Text(
                      '▶ BanterClips',
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w700,
                        color: Colors.white,
                      ),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    ),
  );
}

/// The honest waiting state for a clip that finished rendering but whose URL
/// has not landed yet. This is NOT a failure and must not be drawn as one.
class ClipPreparing extends StatelessWidget {
  const ClipPreparing({super.key});

  @override
  Widget build(BuildContext context) => AspectRatio(
    aspectRatio: 9 / 16,
    child: Container(
      decoration: BoxDecoration(
        color: Colors.black,
        borderRadius: BorderRadius.circular(16),
      ),
      child: const Center(
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('🎬', style: TextStyle(fontSize: 28)),
              SizedBox(height: 10),
              Text(
                'Your video is being prepared',
                style: TextStyle(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                  color: AppColors.text,
                ),
              ),
              SizedBox(height: 6),
              Text(
                "It's finished rendering — check back in a minute.",
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: AppColors.muted),
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
