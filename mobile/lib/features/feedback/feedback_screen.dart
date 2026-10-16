import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../api/errors.dart';
import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';

/// Feedback — the port of `frontend/src/pages/Feedback.jsx`.
///
/// Category, message, an optional star rating. The signed-in account's email
/// travels with it server-side, so there is no email box here. Every note
/// lands in the admin console's Feedback view.
class FeedbackScreen extends ConsumerStatefulWidget {
  const FeedbackScreen({super.key});

  @override
  ConsumerState<FeedbackScreen> createState() => _FeedbackScreenState();
}

class _FeedbackScreenState extends ConsumerState<FeedbackScreen> {
  static const _categories = [
    ('bug', '🐛', "Something's broken"),
    ('idea', '💡', 'An idea'),
    ('praise', '🎉', 'Loved something'),
    ('other', '💬', 'Other'),
  ];
  static const _maxLength = 2000;
  static const _minLength = 5;

  final _message = TextEditingController();
  String _category = 'idea';
  int _rating = 0;
  bool _sending = false;
  bool _sent = false;
  String _error = '';

  @override
  void initState() {
    super.initState();
    _message.addListener(() => setState(() {}));
    ref.read(apiClientProvider).track('feedback_viewed');
  }

  @override
  void dispose() {
    _message.dispose();
    super.dispose();
  }

  bool get _valid =>
      _message.text.trim().length >= _minLength &&
      _message.text.length <= _maxLength;

  Future<void> _send() async {
    if (!_valid || _sending) return;
    setState(() {
      _sending = true;
      _error = '';
    });
    try {
      await ref
          .read(apiClientProvider)
          .sendFeedback(
            message: _message.text.trim(),
            category: _category,
            rating: _rating == 0 ? null : _rating,
            page: '/feedback',
          );
      if (mounted) setState(() => _sent = true);
    } on ApiException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final email = ref.watch(appStateProvider).user?.email ?? '';

    return Scaffold(
      resizeToAvoidBottomInset: true,
      body: SafeArea(
        bottom: false,
        child: ListView(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 32),
          keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          children: [
            Text(
              'Tell us what you think',
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const SizedBox(height: 6),
            const Text(
              'Bugs, ideas, a video that came out wrong, a feature you wish '
              'existed — every note lands in front of the team.',
              style: TextStyle(
                fontSize: 13.5,
                height: 1.5,
                color: AppColors.muted,
              ),
            ),
            const SizedBox(height: 20),
            if (_sent)
              AppCard(
                child: Column(
                  children: [
                    const Text('🙌', style: TextStyle(fontSize: 34)),
                    const SizedBox(height: 8),
                    Text(
                      'Thanks — we read every one.',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleLarge,
                    ),
                    const SizedBox(height: 6),
                    const Text(
                      "Your note went straight to the team. If it needs a "
                      "reply, we'll use your account email.",
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        fontSize: 13.5,
                        height: 1.5,
                        color: AppColors.muted,
                      ),
                    ),
                    const SizedBox(height: 16),
                    GhostButton(
                      label: 'Leave another note',
                      expand: false,
                      height: 44,
                      fontSize: 14,
                      onPressed: () {
                        _message.clear();
                        setState(() {
                          _sent = false;
                          _rating = 0;
                        });
                      },
                    ),
                  ],
                ),
              )
            else
              AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SectionLabel('WHAT IS THIS ABOUT?'),
                    const SizedBox(height: 10),
                    GridView.count(
                      crossAxisCount: 2,
                      shrinkWrap: true,
                      physics: const NeverScrollableScrollPhysics(),
                      mainAxisSpacing: 10,
                      crossAxisSpacing: 10,
                      childAspectRatio: 3.1,
                      children: [
                        for (final (key, emoji, label) in _categories)
                          AppPanel(
                            onTap: () => setState(() => _category = key),
                            color: _category == key
                                ? AppColors.cyanWash(0.08)
                                : AppColors.surface,
                            borderColor: _category == key
                                ? AppColors.cyan
                                : AppColors.border,
                            padding: const EdgeInsets.symmetric(
                              horizontal: 12,
                              vertical: 8,
                            ),
                            child: Row(
                              children: [
                                Text(emoji, style: const TextStyle(fontSize: 18)),
                                const SizedBox(width: 8),
                                Expanded(
                                  child: Text(
                                    label,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: TextStyle(
                                      fontSize: 13,
                                      fontWeight: FontWeight.w700,
                                      color: _category == key
                                          ? AppColors.cyan
                                          : AppColors.text,
                                    ),
                                  ),
                                ),
                              ],
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 20),
                    const SectionLabel('TELL US MORE'),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _message,
                      minLines: 5,
                      maxLines: 8,
                      maxLength: _maxLength,
                      textCapitalization: TextCapitalization.sentences,
                      decoration: InputDecoration(
                        hintText: _category == 'bug'
                            ? 'What happened, and what did you expect? The screen you were on helps.'
                            : 'Be as specific as you like — we read every word.',
                        counterText: '',
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(top: 6, right: 4),
                      child: Align(
                        alignment: Alignment.centerRight,
                        child: Text(
                          '${_message.text.length} / $_maxLength',
                          style: const TextStyle(
                            fontSize: 11.5,
                            color: AppColors.muted2,
                          ),
                        ),
                      ),
                    ),
                    const SizedBox(height: 16),
                    const _LabelWithHint(
                      "HOW'S BANTERCLIPS SO FAR?",
                      'optional',
                    ),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        for (var star = 1; star <= 5; star++)
                          IconButton(
                            onPressed: () => setState(
                              () => _rating = _rating == star ? 0 : star,
                            ),
                            visualDensity: VisualDensity.compact,
                            icon: Opacity(
                              opacity: star <= _rating ? 1 : 0.35,
                              child: const Text(
                                '⭐',
                                style: TextStyle(fontSize: 24),
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 10),
                    Text(
                      "Sent from your account ($email) — we'll reply there if needed.",
                      style: const TextStyle(
                        fontSize: 12.5,
                        color: AppColors.muted2,
                      ),
                    ),
                    if (_error.isNotEmpty) ...[
                      const SizedBox(height: 12),
                      Notice.error(_error),
                    ],
                    const SizedBox(height: 18),
                    GradButton(
                      label: 'Send feedback',
                      loading: _sending,
                      onPressed: _valid ? _send : null,
                    ),
                  ],
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _LabelWithHint extends StatelessWidget {
  const _LabelWithHint(this.label, this.hint);

  final String label;
  final String hint;

  @override
  Widget build(BuildContext context) => Wrap(
    crossAxisAlignment: WrapCrossAlignment.end,
    spacing: 8,
    children: [
      SectionLabel(label),
      Text(
        hint,
        style: const TextStyle(fontSize: 11.5, color: AppColors.muted2),
      ),
    ],
  );
}
