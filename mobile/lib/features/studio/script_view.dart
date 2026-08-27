import 'package:flutter/material.dart';

import '../../models/script.dart';
import '../../theme/app_theme.dart';
import '../../theme/colors.dart';
import '../../theme/typography.dart';
import '../../widgets/surfaces.dart';

/// The script, human-readable: cast, world, and every shot with its
/// dialogue. Port of `frontend/src/components/ScriptView.jsx`.
///
/// With [editable] set, every action and every line becomes a field — the
/// user's own words are what gets performed. Read-only is the "Show script"
/// view on a finished clip.
class ScriptView extends StatelessWidget {
  const ScriptView({
    super.key,
    required this.script,
    this.editable = false,
    this.onEdit,
  });

  final Script script;
  final bool editable;

  /// `(sceneIndex, field, value)` where field is 'line' or 'action'.
  final void Function(int index, String field, String value)? onEdit;

  @override
  Widget build(BuildContext context) => Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '“${script.title}”',
            style: const TextStyle(
              fontSize: 17,
              fontWeight: FontWeight.w800,
              height: 1.3,
              color: AppColors.text,
            ),
          ),
          const SizedBox(height: 5),
          Text(
            [
              '${script.scenes.length} shots',
              '${script.totalSeconds}s',
              if (script.style.isNotEmpty) script.style,
            ].join(' · '),
            style: const TextStyle(fontSize: 12, color: AppColors.muted),
          ),

          // The real-world facts the script was built on. Worth showing:
          // it is the difference between "the AI made something up" and
          // "this is about the game that happened last night".
          if (script.storylines.isNotEmpty) ...[
            const SizedBox(height: 14),
            AppPanel(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text("BUILT ON TODAY'S REAL CONTEXT", style: AppType.microLabel),
                  const SizedBox(height: 6),
                  for (final line in script.storylines.take(4))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 3),
                      child: Text(
                        '• $line',
                        style: const TextStyle(fontSize: 12, height: 1.5, color: AppColors.muted),
                      ),
                    ),
                ],
              ),
            ),
          ],

          if (script.venue.isNotEmpty) ...[
            const SizedBox(height: 14),
            Text.rich(
              TextSpan(
                children: [
                  const TextSpan(text: 'LOCATION (every shot)  ', style: AppType.microLabel),
                  TextSpan(
                    text: script.venue,
                    style: const TextStyle(fontSize: 12.5, height: 1.5, color: AppColors.muted),
                  ),
                ],
              ),
            ),
          ],

          if (script.cast.isNotEmpty) ...[
            const SizedBox(height: 14),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final member in script.cast)
                  Tooltip(
                    message: [
                      if (member.look.isNotEmpty) member.look,
                      if (member.wardrobe.isNotEmpty) 'wearing ${member.wardrobe}',
                    ].join(' — '),
                    child: Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(AppTheme.radiusPill),
                        border: Border.all(color: AppColors.border),
                      ),
                      child: Text(
                        member.name,
                        style: const TextStyle(
                          fontSize: 11.5,
                          fontWeight: FontWeight.w600,
                          color: AppColors.text,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],

          const SizedBox(height: 14),
          for (var i = 0; i < script.scenes.length; i++)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: _ShotCard(
                index: i,
                scene: script.scenes[i],
                speaker: script.speakerLabel(script.scenes[i]),
                editable: editable,
                onEdit: onEdit,
              ),
            ),
        ],
      );
}

class _ShotCard extends StatelessWidget {
  const _ShotCard({
    required this.index,
    required this.scene,
    required this.speaker,
    required this.editable,
    this.onEdit,
  });

  final int index;
  final Scene scene;
  final String speaker;
  final bool editable;
  final void Function(int index, String field, String value)? onEdit;

  @override
  Widget build(BuildContext context) => AppPanel(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Wrap(
              crossAxisAlignment: WrapCrossAlignment.end,
              spacing: 8,
              children: [
                Text(
                  'SHOT ${index + 1}',
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                    color: AppColors.cyan,
                  ),
                ),
                Text(
                  [
                    '${scene.seconds.toStringAsFixed(scene.seconds % 1 == 0 ? 0 : 1)}s',
                    if (scene.beat.isNotEmpty) scene.beat,
                    if (scene.shotSize.isNotEmpty) scene.shotSize,
                    if (scene.cameraMove.isNotEmpty) scene.cameraMove,
                  ].join(' · '),
                  style: const TextStyle(fontSize: 11, color: AppColors.muted2),
                ),
              ],
            ),
            const SizedBox(height: 8),

            // ---- what happens on screen ----------------------------------
            if (editable)
              _EditableField(
                initial: scene.action,
                maxLines: 3,
                fontSize: 13.5,
                onChanged: (value) => onEdit?.call(index, 'action', value),
              )
            else
              Text(
                scene.action,
                style: const TextStyle(fontSize: 13.5, height: 1.5, color: AppColors.text),
              ),

            if (scene.beats.isNotEmpty) ...[
              const SizedBox(height: 7),
              _MetaLine(label: 'TIMING', value: scene.beats),
            ],
            if (scene.expression.isNotEmpty) ...[
              const SizedBox(height: 5),
              _MetaLine(label: 'EXPRESSION', value: scene.expression),
            ],

            const SizedBox(height: 9),

            // ---- the line ------------------------------------------------
            if (editable || !scene.isSilent)
              Container(
                padding: const EdgeInsets.fromLTRB(10, 7, 10, 8),
                decoration: BoxDecoration(
                  color: AppColors.cyanWash(0.06),
                  borderRadius: const BorderRadius.only(
                    topRight: Radius.circular(8),
                    bottomRight: Radius.circular(8),
                  ),
                  border: const Border(
                    left: BorderSide(color: AppColors.cyan, width: 3),
                  ),
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text.rich(
                      TextSpan(
                        style: const TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w700,
                          color: AppColors.cyan,
                        ),
                        children: [
                          TextSpan(text: speaker),
                          if (scene.delivery.isNotEmpty)
                            TextSpan(
                              text: ' · ${scene.delivery}',
                              style: const TextStyle(
                                color: AppColors.muted2,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          if (editable)
                            TextSpan(
                              text: ' · ~${scene.wordBudget} words fit',
                              style: const TextStyle(
                                color: AppColors.muted2,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 4),
                    if (editable)
                      _EditableField(
                        initial: scene.line,
                        maxLines: 2,
                        fontSize: 14,
                        bold: true,
                        hint: '(silent reaction — leave empty)',
                        onChanged: (value) => onEdit?.call(index, 'line', value),
                      )
                    else
                      Text(
                        '“${scene.line}”',
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          height: 1.45,
                          color: AppColors.text,
                        ),
                      ),
                  ],
                ),
              )
            else
              const Text(
                '— silent reaction shot —',
                style: TextStyle(
                  fontSize: 11.5,
                  fontStyle: FontStyle.italic,
                  color: AppColors.muted2,
                ),
              ),
          ],
        ),
      );
}

class _MetaLine extends StatelessWidget {
  const _MetaLine({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) => Text.rich(
        TextSpan(
          children: [
            TextSpan(text: '$label  ', style: AppType.microLabel),
            TextSpan(
              text: value,
              style: const TextStyle(fontSize: 12, height: 1.45, color: AppColors.muted),
            ),
          ],
        ),
      );
}

/// A text field that keeps its own controller.
///
/// This matters: rebuilding the parent on every keystroke (which the draft
/// state does) would otherwise reset the cursor to position zero after each
/// character — the classic "typing backwards" bug.
class _EditableField extends StatefulWidget {
  const _EditableField({
    required this.initial,
    required this.onChanged,
    this.maxLines = 2,
    this.fontSize = 13.5,
    this.bold = false,
    this.hint,
  });

  final String initial;
  final ValueChanged<String> onChanged;
  final int maxLines;
  final double fontSize;
  final bool bold;
  final String? hint;

  @override
  State<_EditableField> createState() => _EditableFieldState();
}

class _EditableFieldState extends State<_EditableField> {
  late final TextEditingController _controller =
      TextEditingController(text: widget.initial);

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => TextField(
        controller: _controller,
        onChanged: widget.onChanged,
        maxLines: widget.maxLines,
        minLines: 1,
        textCapitalization: TextCapitalization.sentences,
        style: TextStyle(
          fontSize: widget.fontSize,
          height: 1.45,
          fontWeight: widget.bold ? FontWeight.w600 : FontWeight.w400,
          color: AppColors.text,
        ),
        decoration: InputDecoration(
          hintText: widget.hint,
          isDense: true,
          contentPadding: const EdgeInsets.symmetric(horizontal: 10, vertical: 9),
        ),
      );
}
