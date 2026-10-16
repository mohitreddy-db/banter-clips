import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../state/app_state.dart';
import '../../theme/colors.dart';
import '../../widgets/surfaces.dart';

const _pages = <(String, String, String)>[
  ('Overview', '/admin/overview', 'Real-time operating picture'),
  ('Users', '/admin/users', 'Growth, plans and account status'),
  ('All Videos', '/admin/videos', 'Every generated clip'),
  ('Generation Jobs', '/admin/jobs', 'Queue, workers and spend controls'),
  ('AI Costs & Quality', '/admin/costs', 'Provider cost and render quality'),
  ('Revenue', '/admin/revenue', 'MRR, conversion and margin'),
  ('Credits', '/admin/credits', 'Pricing and credit readiness'),
  ('Publishing', '/admin/publishing', 'Social delivery status'),
  ('Catalog', '/admin/catalog', 'Characters and reference assets'),
  ('Admins', '/admin/admins', 'Console access'),
  ('Audit Log', '/admin/audit', 'Administrative actions'),
];

class AdminConsoleScreen extends ConsumerStatefulWidget {
  const AdminConsoleScreen({super.key, this.initialSection});

  final String? initialSection;
  @override
  ConsumerState<AdminConsoleScreen> createState() => _AdminConsoleScreenState();
}

class _AdminConsoleScreenState extends ConsumerState<AdminConsoleScreen> {
  int page = 0;
  int days = 7;
  late Future<Map<String, dynamic>> request;

  @override
  void initState() {
    super.initState();
    final section = widget.initialSection;
    if (section != null) {
      final index = _pages.indexWhere(
        (item) => item.$2.split('/').last == section,
      );
      if (index >= 0) page = index;
    }
    request = _load();
  }

  Future<Map<String, dynamic>> _load() {
    final path = _pages[page].$2;
    return ref
        .read(apiClientProvider)
        .adminGet(
          path,
          query: path == '/admin/overview' || path == '/admin/costs'
              ? {'days': days}
              : null,
        );
  }

  void _refresh() => setState(() => request = _load());

  @override
  Widget build(BuildContext context) {
    if (ref.watch(appStateProvider).user?.isAdmin != true) {
      return Scaffold(
        appBar: AppBar(),
        body: const Center(child: Text('Admin access required.')),
      );
    }
    final selected = _pages[page];
    return Scaffold(
      appBar: AppBar(
        leading: IconButton(
          onPressed: context.pop,
          icon: const Icon(Icons.arrow_back),
        ),
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('BanterClips', style: TextStyle(fontSize: 16)),
            Text(
              'ADMIN CONSOLE',
              style: TextStyle(
                fontSize: 9,
                letterSpacing: 1.2,
                color: AppColors.cyan,
              ),
            ),
          ],
        ),
        actions: [
          IconButton(
            onPressed: _refresh,
            icon: const Icon(Icons.refresh_rounded),
          ),
        ],
      ),
      body: Column(
        children: [
          SizedBox(
            height: 48,
            child: ListView.separated(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 5),
              scrollDirection: Axis.horizontal,
              itemCount: _pages.length,
              separatorBuilder: (_, __) => const SizedBox(width: 6),
              itemBuilder: (_, i) => ChoiceChip(
                label: Text(_pages[i].$1),
                selected: page == i,
                onSelected: (_) {
                  final segment = _pages[i].$2.split('/').last;
                  context.go(i == 0 ? '/admin' : '/admin/$segment');
                },
              ),
            ),
          ),
          const Divider(),
          Expanded(
            child: FutureBuilder<Map<String, dynamic>>(
              future: request,
              builder: (_, snapshot) {
                if (snapshot.connectionState != ConnectionState.done) {
                  return const Center(child: CircularProgressIndicator());
                }
                if (snapshot.hasError) {
                  return ListView(
                    padding: const EdgeInsets.all(20),
                    children: [
                      Notice(
                        text: snapshot.error.toString(),
                        icon: Icons.error_outline,
                      ),
                    ],
                  );
                }
                return RefreshIndicator(
                  onRefresh: () async {
                    final next = _load();
                    setState(() => request = next);
                    await next;
                  },
                  child: _AdminPage(
                    title: selected.$1,
                    subtitle: selected.$3,
                    data: snapshot.data ?? const {},
                    days: days,
                    showDays:
                        selected.$2 == '/admin/overview' ||
                        selected.$2 == '/admin/costs',
                    onDays: (value) => setState(() {
                      days = value;
                      request = _load();
                    }),
                  ),
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _AdminPage extends StatelessWidget {
  const _AdminPage({
    required this.title,
    required this.subtitle,
    required this.data,
    required this.days,
    required this.showDays,
    required this.onDays,
  });
  final String title, subtitle;
  final Map<String, dynamic> data;
  final int days;
  final bool showDays;
  final ValueChanged<int> onDays;

  @override
  Widget build(BuildContext context) {
    final metrics = _metrics(data);
    final collections = data.entries.where((e) => e.value is List).toList();
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        Text(title, style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 4),
        Text(subtitle, style: Theme.of(context).textTheme.bodySmall),
        if (showDays) ...[
          const SizedBox(height: 14),
          SegmentedButton<int>(
            segments: const [
              ButtonSegment(value: 1, label: Text('Today')),
              ButtonSegment(value: 7, label: Text('7 Days')),
              ButtonSegment(value: 30, label: Text('30 Days')),
            ],
            selected: {days},
            onSelectionChanged: (value) => onDays(value.first),
          ),
        ],
        const SizedBox(height: 16),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithMaxCrossAxisExtent(
            maxCrossAxisExtent: 220,
            childAspectRatio: 1.55,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
          ),
          itemCount: metrics.length,
          itemBuilder: (_, i) =>
              _Metric(label: metrics[i].$1, value: metrics[i].$2),
        ),
        for (final entry in collections) ...[
          const SizedBox(height: 16),
          _Bars(
            title: _label(entry.key),
            rows: List<dynamic>.from(entry.value as List),
          ),
        ],
        if (metrics.isEmpty && collections.isEmpty)
          const AppCard(
            child: Text(
              'No data available yet.',
              style: TextStyle(color: AppColors.muted),
            ),
          ),
      ],
    );
  }
}

class _Metric extends StatelessWidget {
  const _Metric({required this.label, required this.value});
  final String label, value;
  @override
  Widget build(BuildContext context) => AppCard(
    padding: const EdgeInsets.all(14),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label.toUpperCase(),
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(
            fontSize: 9.5,
            fontWeight: FontWeight.w700,
            letterSpacing: .8,
            color: AppColors.muted2,
          ),
        ),
        const Spacer(),
        Text(
          value,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 3),
        const Text(
          'live API value',
          style: TextStyle(fontSize: 10.5, color: AppColors.muted),
        ),
      ],
    ),
  );
}

class _Bars extends StatelessWidget {
  const _Bars({required this.title, required this.rows});
  final String title;
  final List<dynamic> rows;

  @override
  Widget build(BuildContext context) {
    final mapped = rows
        .whereType<Map>()
        .map((e) => Map<String, dynamic>.from(e))
        .toList();
    var max = 1.0;
    for (final row in mapped) {
      for (final value in row.values.whereType<num>()) {
        if (value.toDouble() > max) max = value.toDouble();
      }
    }
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 12),
          if (rows.isEmpty)
            const Text(
              'Nothing here yet.',
              style: TextStyle(color: AppColors.muted2),
            ),
          for (final raw in rows.take(12)) _BarRow(raw: raw, max: max),
        ],
      ),
    );
  }
}

class _BarRow extends StatelessWidget {
  const _BarRow({required this.raw, required this.max});
  final dynamic raw;
  final double max;
  @override
  Widget build(BuildContext context) {
    final row = raw is Map
        ? Map<String, dynamic>.from(raw as Map)
        : <String, dynamic>{'value': raw};
    final text =
        row.values.whereType<String>().firstOrNull ??
        '${row.values.firstOrNull ?? ''}';
    final number = row.values.whereType<num>().lastOrNull;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  text,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 12.5,
                    color: AppColors.muted,
                  ),
                ),
              ),
              Text(
                number == null ? '' : _format(number),
                style: const TextStyle(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          if (number != null) ...[
            const SizedBox(height: 6),
            ClipRRect(
              borderRadius: BorderRadius.circular(99),
              child: LinearProgressIndicator(
                value: (number.toDouble() / max).clamp(0, 1),
                minHeight: 9,
                backgroundColor: AppColors.panel,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

List<(String, String)> _metrics(Map<String, dynamic> data) {
  final result = <(String, String)>[];
  void walk(String prefix, Map<String, dynamic> map) {
    for (final entry in map.entries) {
      final key = prefix.isEmpty ? entry.key : '$prefix ${entry.key}';
      final value = entry.value;
      if ((value is num || value is bool || value is String) &&
          !entry.key.contains('url') &&
          '$value'.length < 40 &&
          result.length < 12) {
        result.add((_label(key), _format(value)));
      } else if (value is Map && result.length < 12) {
        walk(key, Map<String, dynamic>.from(value));
      }
    }
  }

  walk('', data);
  return result;
}

String _label(String key) => key
    .replaceAll('_', ' ')
    .split(' ')
    .map(
      (word) =>
          word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1)}',
    )
    .join(' ');
String _format(dynamic value) => value is bool
    ? (value ? 'Yes' : 'No')
    : value is double
    ? value.toStringAsFixed(value.abs() < 1 ? 2 : 1)
    : '$value';
