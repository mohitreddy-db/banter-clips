import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:share_plus/share_plus.dart';

import '../../api/errors.dart';
import '../../models/clip.dart';
import '../../models/script.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/states.dart';
import '../../widgets/surfaces.dart';
import '../account/upgrade_sheet.dart';
import '../clips/clip_player.dart';
import '../clips/publish_sheet.dart';
import 'script_view.dart';

/// One clip, from script approval through rendering to the finished video.
///
/// On the web these are phases of `Studio.jsx`; here they are one pushed
/// route, so the back gesture always means "leave this clip" and the studio
/// stays a clean sheet to write the next take on.
///
/// ## Polling, and why it stops
///
/// The web polls every 900 ms forever — a browser tab can. A phone cannot:
/// iOS suspends the process seconds after the user leaves, and Android kills
/// it under memory pressure, so a timer left running is a battery complaint
/// and a leak, not a feature. This screen therefore:
///
///   * polls every 2.5 s while it is on screen and the app is in the
///     foreground,
///   * stops the moment the app is backgrounded, and
///   * refetches once immediately on resume, which is what actually catches
///     the user up.
///
/// The proper fix for a job that finishes while the app is closed is a push
/// notification from the worker (v2 — it needs `POST /me/devices` and a
/// Firebase project). Until then the copy tells the truth: leave the app,
/// the render carries on, and it will be waiting in My Clips.
class ClipScreen extends ConsumerStatefulWidget {
  const ClipScreen({super.key, required this.clipId});

  final String clipId;

  @override
  ConsumerState<ClipScreen> createState() => _ClipScreenState();
}

class _ClipScreenState extends ConsumerState<ClipScreen>
    with WidgetsBindingObserver {
  static const _pollInterval = Duration(seconds: 2, milliseconds: 500);

  Clip? _clip;
  Timer? _poll;
  Timer? _tick;

  /// Wall-clock arithmetic rather than a counter: it survives the screen
  /// being reopened mid-render and the app being backgrounded.
  DateTime? _startedAt;
  int _elapsed = 0;

  /// The editable working copy of the script. Null until one arrives.
  Script? _draft;
  Script? _draftBase;

  bool _loading = true;
  String _busy = '';
  String _error = '';

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _stopTimers();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) {
      _refetch();
      _startTimersIfNeeded();
    } else {
      _stopTimers();
    }
  }

  Future<void> _load() async {
    try {
      final clip = await ref.read(apiClientProvider).getClip(widget.clipId);
      if (!mounted) return;
      setState(() {
        _clip = clip;
        _loading = false;
      });
      _adoptScript(clip);
      // Count from when the job actually started, not from when this screen
      // happened to open — reopening a running clip must not reset the clock.
      _startedAt = clip.createdAt ?? DateTime.now();
      _startTimersIfNeeded();
    } on ApiException catch (e) {
      if (mounted) {
        setState(() {
          _error = e.message;
          _loading = false;
        });
      }
    }
  }

  /// Take a fresh copy of the script whenever a new one arrives, keeping the
  /// original alongside it so we can send only what changed.
  void _adoptScript(Clip clip) {
    final script = clip.script;
    if (!clip.awaitingScript || script == null) return;
    if (_draftBase != null && identical(_draftBase, script)) return;
    _draftBase = script;
    _draft = script.withScenes([...script.scenes]);
  }

  void _startTimersIfNeeded() {
    final clip = _clip;
    if (clip == null || !clip.inFlight) return;
    _poll ??= Timer.periodic(_pollInterval, (_) => _refetch());
    _tick ??= Timer.periodic(const Duration(seconds: 1), (_) {
      final start = _startedAt;
      if (start == null || !mounted) return;
      setState(
        () => _elapsed = DateTime.now()
            .difference(start)
            .inSeconds
            .clamp(0, 1 << 30),
      );
    });
  }

  void _stopTimers() {
    _poll?.cancel();
    _tick?.cancel();
    _poll = null;
    _tick = null;
  }

  Future<void> _refetch() async {
    try {
      final clip = await ref.read(apiClientProvider).getClip(widget.clipId);
      if (!mounted) return;
      setState(() => _clip = clip);
      _adoptScript(clip);
      ref.read(appStateProvider.notifier).mergeClip(clip);
      if (!clip.inFlight) {
        _stopTimers();
        // A finished render changes the allowance; a finished script does not.
        if (clip.isReady) ref.read(appStateProvider.notifier).refreshUsage();
      }
    } on ApiException {
      // Transient poll failure — keep the last known state and try again.
    }
  }

  /// Wraps an action that changes the clip: one busy flag, one error line.
  Future<void> _act(String tag, Future<Clip> Function() action) async {
    setState(() {
      _busy = tag;
      _error = '';
    });
    try {
      final clip = await action();
      if (!mounted) return;
      setState(() => _clip = clip);
      _adoptScript(clip);
      ref.read(appStateProvider.notifier).mergeClip(clip);
      // A retry or an approval starts the clock now — created_at is when the
      // clip was first made, which could be minutes or days ago.
      _startedAt = DateTime.now();
      _elapsed = 0;
      _startTimersIfNeeded();
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _busy = '');
    }
  }

  void _editDraft(int index, String field, String value) {
    final draft = _draft;
    if (draft == null || index >= draft.scenes.length) return;
    final scenes = [...draft.scenes];
    scenes[index] = field == 'line'
        ? scenes[index].copyWith(line: value)
        : scenes[index].copyWith(action: value);
    // No setState: the fields hold their own controllers, so rebuilding here
    // would be wasted work on every keystroke.
    _draft = draft.withScenes(scenes);
  }

  List<Map<String, dynamic>> get _edits {
    final draft = _draft;
    final base = _draftBase;
    if (draft == null || base == null) return const [];
    return draft.diffAgainst(base);
  }

  Future<void> _approve() => _act('approve', () async {
    final api = ref.read(apiClientProvider);
    final edits = _edits;
    if (edits.isNotEmpty) await api.updateScript(widget.clipId, edits);
    return api.approveScript(widget.clipId);
  });

  Future<void> _share() async {
    final clip = _clip;
    if (clip == null) return;
    setState(() {
      _busy = 'share';
      _error = '';
    });
    try {
      final file = await ref.read(apiClientProvider).downloadClip(clip);
      if (!mounted) return;
      // The native share sheet — save to camera roll, send to WhatsApp, post
      // anywhere. This is the one moment the app is plainly better than the
      // website, which can only drop a file in the Downloads folder.
      // iPad presents the share sheet as a popover and throws if it is given no
      // anchor to point at. The app supports iPad, so the rect is not optional.
      final box = context.findRenderObject() as RenderBox?;
      await Share.shareXFiles(
        [XFile(file.path)],
        text: clip.take,
        sharePositionOrigin: box != null
            ? box.localToGlobal(Offset.zero) & box.size
            : null,
      );
      ref.read(apiClientProvider).track('video_downloaded', {
        'clip_id': clip.id,
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.needsUpgrade || e.status == 403) {
        showUpgradeSheet(context, reason: UpgradeReason.download);
      } else {
        setState(() => _error = e.message);
      }
    } finally {
      if (mounted) setState(() => _busy = '');
    }
  }

  @override
  Widget build(BuildContext context) {
    final clip = _clip;

    return Scaffold(
      appBar: AppBar(
        title: Text(clip == null ? 'Clip' : '${clip.sport} · ${clip.tone}'),
        actions: [
          if (clip?.script != null && clip!.isReady)
            IconButton(
              tooltip: 'Show script',
              icon: const Icon(Icons.description_outlined),
              onPressed: () => _showScriptDialog(clip.script!),
            ),
        ],
      ),
      body: SafeArea(
        top: false,
        child: _loading
            ? const Center(child: InlineSpinner(size: 26))
            : clip == null
            ? ErrorState(
                message: _error.isEmpty
                    ? 'That clip could not be opened.'
                    : _error,
                onRetry: _load,
              )
            : RefreshIndicator(
                onRefresh: _refetch,
                color: AppColors.cyan,
                backgroundColor: AppColors.surface,
                child: ListView(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
                  children: [
                    if (clip.awaitingScript)
                      ..._scriptPhase(clip)
                    else if (clip.hasFailed)
                      ..._failedPhase(clip)
                    else if (clip.isReady)
                      ..._readyPhase(clip)
                    else
                      ..._generatingPhase(clip),
                  ],
                ),
              ),
      ),
    );
  }

  // ------------------------------------------------------------- phases

  List<Widget> _scriptPhase(Clip clip) => [
    const Notice(
      text:
          'Your script is ready — read it through. Nothing is generated, '
          'and nothing is used up, until you approve.',
      icon: Icons.edit_note_rounded,
    ),
    const SizedBox(height: 16),
    AppCard(
      child: ScriptView(
        script: _draft ?? clip.script!,
        editable: true,
        onEdit: _editDraft,
      ),
    ),
    const SizedBox(height: 10),
    const Text(
      '✏️ Every line and action above is editable — your words are what gets performed.',
      style: TextStyle(fontSize: 12, color: AppColors.muted2),
    ),
    if (_error.isNotEmpty) ...[
      const SizedBox(height: 14),
      Notice.error(_error),
    ],
    const SizedBox(height: 18),
    GradButton(
      label: '✅  Approve script & generate video',
      height: 54,
      loading: _busy == 'approve',
      onPressed: _busy.isEmpty ? _approve : null,
    ),
    const SizedBox(height: 12),
    AppPanel(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Not quite right?',
            style: TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppColors.text,
            ),
          ),
          const SizedBox(height: 10),
          _RegenerateField(
            busy: _busy == 'regen',
            onSubmit: (feedback) => _act(
              'regen',
              () => ref
                  .read(apiClientProvider)
                  .regenerateScript(widget.clipId, feedback: feedback),
            ),
          ),
        ],
      ),
    ),
  ];

  List<Widget> _generatingPhase(Clip clip) {
    final stageIndex = clip.stageIndex;
    return [
      AppCard(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Expanded(
                  child: Text(
                    'Generating your video…',
                    style: Theme.of(context).textTheme.titleLarge,
                  ),
                ),
                Text(
                  '${_formatElapsed(_elapsed)} elapsed',
                  style: const TextStyle(fontSize: 13, color: AppColors.muted),
                ),
              ],
            ),
            const SizedBox(height: 14),
            for (var i = 0; i < ClipStage.values.length; i++)
              _StageRow(
                label: ClipStage.values[i].label,
                state: clip.status == 'queued'
                    ? _StageState.pending
                    : i < stageIndex
                    ? _StageState.done
                    : i == stageIndex
                    ? _StageState.active
                    : _StageState.pending,
              ),
          ],
        ),
      ),
      // One line, always the current one. The stage rows above move every
      // minute or two; this moves every few seconds, and that is what makes
      // a four-minute wait feel alive rather than stuck.
      if ((clip.currentStep ?? '').isNotEmpty) ...[
        const SizedBox(height: 14),
        AppPanel(
          color: AppColors.cyanWash(0.06),
          borderColor: AppColors.cyan.withValues(alpha: 0.18),
          padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
          child: Row(
            children: [
              const InlineSpinner(size: 16),
              const SizedBox(width: 12),
              Expanded(
                child: Text(
                  clip.currentStep!,
                  style: const TextStyle(
                    fontSize: 14.5,
                    fontWeight: FontWeight.w600,
                    color: AppColors.text,
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
      const SizedBox(height: 14),
      const Notice(
        text:
            'You can leave the app — your video keeps rendering on our '
            'servers and will be waiting in My Clips.',
        icon: Icons.info_outline_rounded,
      ),
      if (clip.isSimulated) ...[
        const SizedBox(height: 12),
        const Notice(
          text:
              'Demo run: the real stages at real pacing, but nothing is '
              'generated and no allowance is used.',
          icon: Icons.science_outlined,
        ),
      ],
    ];
  }

  List<Widget> _failedPhase(Clip clip) => [
    AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: AppColors.errorWash(0.14),
                  borderRadius: BorderRadius.circular(13),
                ),
                child: const Center(
                  child: Text('⚠️', style: TextStyle(fontSize: 19)),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Generation failed',
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 2),
                    const Text(
                      'Your allowance was not used.',
                      style: TextStyle(fontSize: 13, color: AppColors.muted),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if ((clip.error ?? '').isNotEmpty) ...[
            const SizedBox(height: 14),
            Text(
              clip.error!,
              style: const TextStyle(
                fontSize: 14,
                height: 1.55,
                color: AppColors.muted,
              ),
            ),
          ],
        ],
      ),
    ),
    if (_error.isNotEmpty) ...[
      const SizedBox(height: 14),
      Notice.error(_error),
    ],
    const SizedBox(height: 18),
    GradButton(
      label: '↻  Retry for free',
      loading: _busy == 'retry',
      onPressed: () => _act(
        'retry',
        () => ref.read(apiClientProvider).retryClip(widget.clipId),
      ),
    ),
  ];

  List<Widget> _readyPhase(Clip clip) {
    final state = ref.watch(appStateProvider);
    return [
      Notice(
        text:
            'Video ready · 0:${clip.displaySeconds.toString().padLeft(2, '0')}',
        tone: NoticeTone.success,
        icon: Icons.check_circle_outline_rounded,
      ),
      const SizedBox(height: 14),
      AppPanel(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        child: Text(
          '“${clip.take}”',
          style: const TextStyle(
            fontSize: 14.5,
            height: 1.5,
            fontWeight: FontWeight.w600,
            color: AppColors.text,
          ),
        ),
      ),
      const SizedBox(height: 16),
      Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 300),
          child: clip.isPreparing
              ? const ClipPreparing()
              : ClipPlayer(
                  url: clip.videoUrl!,
                  watermarked: clip.watermarked,
                  onPlay: () =>
                      ref.read(apiClientProvider).track('preview_played'),
                ),
        ),
      ),
      const SizedBox(height: 20),
      GradButton(
        label: 'Publish to Instagram',
        height: 54,
        onPressed: clip.isPreparing
            ? null
            : () => showPublishSheet(context, clip),
      ),
      const SizedBox(height: 10),
      if (state.canDownload)
        GhostButton(
          label: 'Share · save without watermark',
          icon: Icons.ios_share_rounded,
          loading: _busy == 'share',
          onPressed: clip.isPreparing ? null : _share,
        )
      else
        GhostButton(
          label: 'Share in HD',
          icon: Icons.lock_outline_rounded,
          dashed: true,
          color: AppColors.muted2,
          trailing: const CreatorPill(),
          onPressed: () =>
              showUpgradeSheet(context, reason: UpgradeReason.download),
        ),
      if (clip.script != null) ...[
        const SizedBox(height: 10),
        GhostButton(
          label: '📝  Show script',
          color: AppColors.muted,
          onPressed: () => _showScriptDialog(clip.script!),
        ),
      ],
      if (_error.isNotEmpty) ...[
        const SizedBox(height: 14),
        Notice.error(_error),
      ],
      const SizedBox(height: 18),
      AppPanel(
        padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 16),
        child: Column(
          children: [
            for (final (label, value) in [
              ('Resolution', clip.resolutionLabel),
              ('Duration', '${clip.displaySeconds}s'),
              ('Format', 'MP4 · H.264/AAC'),
              (
                'Watermark',
                clip.watermarked ? 'BanterClips (Free plan)' : 'None (Creator)',
              ),
            ])
              Padding(
                padding: const EdgeInsets.only(bottom: 10),
                child: Row(
                  children: [
                    Text(
                      label,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.muted,
                      ),
                    ),
                    const Spacer(),
                    Text(
                      value,
                      style: const TextStyle(
                        fontSize: 13,
                        fontWeight: FontWeight.w600,
                        color: AppColors.text,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    ];
  }

  void _showScriptDialog(Script script) => showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    backgroundColor: AppColors.surface,
    builder: (context) => DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      builder: (context, controller) => ListView(
        controller: controller,
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 28),
        children: [ScriptView(script: script)],
      ),
    ),
  );

  static String _formatElapsed(int seconds) =>
      '${seconds ~/ 60}:${(seconds % 60).toString().padLeft(2, '0')}';
}

enum _StageState { done, active, pending }

class _StageRow extends StatelessWidget {
  const _StageRow({required this.label, required this.state});

  final String label;
  final _StageState state;

  @override
  Widget build(BuildContext context) {
    final (icon, color, trailing) = switch (state) {
      _StageState.done => (
        const Icon(
          Icons.check_circle_rounded,
          size: 21,
          color: AppColors.green,
        ),
        AppColors.text,
        'done',
      ),
      _StageState.active => (
        const InlineSpinner(size: 20),
        AppColors.cyan,
        'in progress',
      ),
      _StageState.pending => (
        const Icon(Icons.circle_outlined, size: 21, color: AppColors.border),
        AppColors.muted2,
        'queued',
      ),
    };

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Row(
        children: [
          SizedBox(width: 22, child: Center(child: icon)),
          const SizedBox(width: 13),
          Expanded(
            child: Text(
              label,
              style: TextStyle(
                fontSize: 14.5,
                fontWeight: state == _StageState.active
                    ? FontWeight.w600
                    : FontWeight.w500,
                color: color,
              ),
            ),
          ),
          Text(
            trailing,
            style: TextStyle(
              fontSize: 11.5,
              color: switch (state) {
                _StageState.done => AppColors.green,
                _StageState.active => AppColors.cyan,
                _StageState.pending => AppColors.muted2,
              },
            ),
          ),
        ],
      ),
    );
  }
}

/// "Write a different script" — free, because only the render costs money
/// and it has not started.
class _RegenerateField extends StatefulWidget {
  const _RegenerateField({required this.busy, required this.onSubmit});

  final bool busy;
  final void Function(String feedback) onSubmit;

  @override
  State<_RegenerateField> createState() => _RegenerateFieldState();
}

class _RegenerateFieldState extends State<_RegenerateField> {
  final _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      TextField(
        controller: _controller,
        maxLines: 2,
        minLines: 1,
        style: const TextStyle(fontSize: 13.5, color: AppColors.text),
        decoration: const InputDecoration(
          hintText:
              'Optional: what should change? e.g. “funnier, set it in the press room”',
          isDense: true,
        ),
      ),
      const SizedBox(height: 10),
      GhostButton(
        label: '↻  Write a different script (free)',
        height: 46,
        fontSize: 14,
        loading: widget.busy,
        onPressed: () => widget.onSubmit(_controller.text.trim()),
      ),
    ],
  );
}
