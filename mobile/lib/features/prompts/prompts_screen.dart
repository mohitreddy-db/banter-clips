import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../theme/colors.dart';
import '../../widgets/surfaces.dart';

class PromptsScreen extends StatefulWidget {
  const PromptsScreen({super.key});

  @override
  State<PromptsScreen> createState() => _PromptsScreenState();
}

class _PromptsScreenState extends State<PromptsScreen> {
  String _filter = 'All';

  static const _prompts =
      <({String title, String prompt, String sport, String tone})>[
        (
          title: 'GOAT Debate',
          prompt: '[Player] is the GOAT and it is not even close.',
          sport: 'NBA',
          tone: 'Bold',
        ),
        (
          title: 'Overrated',
          prompt: '[Player or team] is the most overrated name in the league.',
          sport: 'NFL',
          tone: 'Savage',
        ),
        (
          title: 'Hot Take',
          prompt: 'Nobody wants to admit it, but [your sports take].',
          sport: 'Soccer',
          tone: 'Bold',
        ),
        (
          title: 'Post-game Roast',
          prompt: '[Team] did not lose the game — they donated it.',
          sport: 'NBA',
          tone: 'Funny',
        ),
        (
          title: 'Prediction',
          prompt: 'Save this: [team] will win it all this season.',
          sport: 'MLB',
          tone: 'Hype',
        ),
        (
          title: 'Unpopular Opinion',
          prompt: 'Unpopular opinion: [player] makes this team worse.',
          sport: 'NFL',
          tone: 'Savage',
        ),
        (
          title: 'Comeback Story',
          prompt: '[Player] is about to silence every critic this season.',
          sport: 'Soccer',
          tone: 'Hype',
        ),
        (
          title: 'Fan Reality Check',
          prompt: '[Team] fans need to hear the truth: [your take].',
          sport: 'NBA',
          tone: 'Funny',
        ),
      ];

  @override
  Widget build(BuildContext context) {
    final shown = _filter == 'All'
        ? _prompts
        : _prompts.where((p) => p.sport == _filter).toList();
    return Scaffold(
      appBar: AppBar(title: const Text('Prompts')),
      body: ListView(
        padding: const EdgeInsets.fromLTRB(16, 10, 16, 30),
        children: [
          const Text(
            'Creator templates',
            style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 7),
          const Text(
            'Proven starting points for debates, reactions, predictions and roasts. Tap one and make it yours.',
            style: TextStyle(color: AppColors.muted, height: 1.45),
          ),
          const SizedBox(height: 18),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final sport in const ['All', 'NBA', 'NFL', 'Soccer', 'MLB'])
                ChoiceChip(
                  label: Text(sport),
                  selected: _filter == sport,
                  onSelected: (_) => setState(() => _filter = sport),
                ),
            ],
          ),
          const SizedBox(height: 18),
          for (final p in shown) ...[
            AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          p.title,
                          style: const TextStyle(
                            fontSize: 17,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                      Text(
                        p.sport,
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppColors.cyan,
                          fontWeight: FontWeight.w700,
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 9),
                  Text(
                    p.prompt,
                    style: const TextStyle(
                      fontSize: 14,
                      height: 1.45,
                      color: AppColors.muted,
                    ),
                  ),
                  const SizedBox(height: 13),
                  Row(
                    children: [
                      Text(
                        p.tone,
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppColors.muted2,
                        ),
                      ),
                      const Spacer(),
                      FilledButton.tonal(
                        onPressed: () => context.go(
                          '/studio?prompt=${Uri.encodeQueryComponent(p.prompt)}&sport=${p.sport}&tone=${p.tone}',
                        ),
                        child: const Text('Use prompt →'),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 10),
          ],
        ],
      ),
    );
  }
}
