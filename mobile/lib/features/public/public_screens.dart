import 'dart:async';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:video_player/video_player.dart';

import '../../theme/colors.dart';
import '../../state/app_state.dart';
import '../../widgets/buttons.dart';
import '../../widgets/surfaces.dart';
import '../account/upgrade_sheet.dart';

const _showcaseBase =
    'https://taphbakizdagamimbhjh.supabase.co/storage/v1/object/public/clips/showcase';

const _clips = <({String slug, String sport, String take, String blurb})>[
  (
    slug: 'mbappe-cone-drills',
    sport: 'Soccer',
    take: "Mbappé just turned Real Sociedad's defense into cone drills.",
    blurb:
        'A penalty-box wind-up staged as a broadcast moment—script, casting, voiceover and captions generated from one take.',
  ),
  (
    slug: 'lewis-skelly-vs-yamal',
    sport: 'Soccer',
    take: "Lewis-Skelly is as good as Yamal — so where's the fuss?",
    blurb:
        'The height gap played as hide-and-seek in the paint, generated from a single sentence.',
  ),
  (
    slug: 'arsenal-trust-the-process',
    sport: 'Soccer',
    take:
        'Arsenal bottled the title again and the fans still say trust the process.',
    blurb:
        'A tall joke taken literally, with burned-in captions timed to the punchline.',
  ),
  (
    slug: 'arsenal-undefeated-2026',
    sport: 'Soccer',
    take: 'Arsenal fans are acting undefeated — give it two weeks.',
    blurb: 'The GOAT debate staged, scripted and voiced from one written take.',
  ),
  (
    slug: 'klay-south-beach',
    sport: 'NBA',
    take:
        'Klay Thompson and Spoelstra might cook up Heat basketball that makes Giannis sweat.',
    blurb:
        'A dead-serious eulogy for a 29-point lead, rendered in a savage tone.',
  ),
  (
    slug: 'mourinho-mop-meltdown',
    sport: 'Soccer',
    take:
        "Mourinho at Real Madrid again? I'm rehearsing my sideline meltdowns with a mop.",
    blurb: 'A finished 9:16 clip with commentary, crowd noise and captions.',
  ),
];

String _poster(String slug) => '$_showcaseBase/$slug/poster.jpg';
String _video(String slug) => '$_showcaseBase/$slug/final.mp4';

class BrandMark extends StatelessWidget {
  const BrandMark({super.key, this.compact = false});
  final bool compact;
  @override
  Widget build(BuildContext context) => Image.asset(
    'assets/images/banterclips-logo.png',
    width: compact ? 34 : 44,
    height: compact ? 34 : 44,
    filterQuality: FilterQuality.high,
  );
}

class PublicHeader extends StatelessWidget implements PreferredSizeWidget {
  const PublicHeader({super.key});
  @override
  Size get preferredSize => const Size.fromHeight(60);
  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) => AppBar(
      leadingWidth: 0,
      leading: const SizedBox.shrink(),
      title: GestureDetector(
        onTap: () => context.go('/'),
        child: const BrandMark(),
      ),
      actions: [
        if (constraints.maxWidth > 480)
          TextButton(
            onPressed: () => context.go('/sign-in'),
            child: const Text('Sign in'),
          ),
        Padding(
          padding: const EdgeInsets.only(right: 12),
          child: FilledButton(
            onPressed: () => context.go('/sign-in'),
            child: const Text('Start Free'),
          ),
        ),
      ],
    ),
  );
}

class LandingScreen extends StatelessWidget {
  const LandingScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const PublicHeader(),
    body: ListView(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 42, 20, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const _Eyebrow('AI SPORTS VIDEO STUDIO'),
              const SizedBox(height: 16),
              Text(
                'BanterClips Turns Any Sports Opinion Into A Viral Video In Seconds.',
                style: GoogleFonts.spaceGrotesk(
                  fontSize: 42,
                  height: 1.05,
                  letterSpacing: -1.4,
                  fontWeight: FontWeight.w700,
                  color: AppColors.text,
                ),
              ),
              const SizedBox(height: 18),
              const Text(
                'Create AI-powered sports banter, predictions, reactions and debates—ready for TikTok, Instagram Reels and YouTube Shorts.',
                style: TextStyle(
                  fontSize: 17,
                  height: 1.55,
                  color: AppColors.muted,
                ),
              ),
              const SizedBox(height: 24),
              GradButton(
                label: 'Start Creating Free →',
                onPressed: () => context.go('/sign-in'),
              ),
              const SizedBox(height: 12),
              GhostButton(
                label: 'Watch Demo',
                onPressed: () => context.go('/showcase/mbappe-cone-drills'),
              ),
              const SizedBox(height: 16),
              const Text(
                'No credit card · First video free · Export in 9:16',
                style: TextStyle(fontSize: 12, color: AppColors.muted2),
              ),
              const SizedBox(height: 34),
              const _StudioDemo(),
            ],
          ),
        ),
        const _TrustStrip(),
        const _LandingSection(
          eyebrow: 'EVERYTHING, AUTOMATED',
          title: 'One opinion in. A finished video out.',
          children: [
            _Feature(
              icon: Icons.movie_creation_outlined,
              title: 'AI Video Generator',
              text: 'Type an opinion, get a finished 9:16 sports video.',
            ),
            _Feature(
              icon: Icons.record_voice_over_outlined,
              title: 'AI Voiceovers',
              text:
                  'Characters speak their lines, lip-synced with crowd noise.',
            ),
            _Feature(
              icon: Icons.closed_caption_outlined,
              title: 'Animated Captions',
              text: 'Burned in and timed so every line lands with sound off.',
            ),
            _Feature(
              icon: Icons.send_rounded,
              title: 'One-Click Publishing',
              text: 'Publish directly when the render is ready.',
            ),
            _Feature(
              icon: Icons.tune_rounded,
              title: 'Tone Control',
              text:
                  'Funny, savage, hype or bold changes the script and lighting.',
            ),
          ],
        ),
        const _HowItWorks(),
        Padding(
          padding: const EdgeInsets.fromLTRB(20, 36, 20, 12),
          child: Row(
            children: [
              const Expanded(
                child: Text(
                  'Made with BanterClips',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
                ),
              ),
              TextButton(
                onPressed: () => context.go('/showcase'),
                child: const Text('See all →'),
              ),
            ],
          ),
        ),
        SizedBox(
          height: 320,
          child: ListView.separated(
            padding: const EdgeInsets.symmetric(horizontal: 20),
            scrollDirection: Axis.horizontal,
            itemCount: _clips.length,
            separatorBuilder: (_, __) => const SizedBox(width: 12),
            itemBuilder: (_, i) =>
                SizedBox(width: 170, child: ShowcaseCard(clip: _clips[i])),
          ),
        ),
        const _Testimonials(),
        const _Stats(),
        Padding(
          padding: const EdgeInsets.all(20),
          child: AppCard(
            child: Column(
              children: [
                const Text(
                  'Simple, creator-friendly pricing',
                  style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Publish free. Upgrade to download without the watermark.',
                  textAlign: TextAlign.center,
                  style: TextStyle(color: AppColors.muted),
                ),
                const SizedBox(height: 18),
                GradButton(
                  label: r'View $19 Creator plan',
                  onPressed: () => context.go('/pricing'),
                ),
              ],
            ),
          ),
        ),
        const _FinalCta(),
        const _Footer(),
      ],
    ),
  );
}

class _StudioDemo extends StatefulWidget {
  const _StudioDemo();
  @override
  State<_StudioDemo> createState() => _StudioDemoState();
}

class _StudioDemoState extends State<_StudioDemo> {
  late final VideoPlayerController _video;

  @override
  void initState() {
    super.initState();
    _video =
        VideoPlayerController.networkUrl(
            Uri.parse('$_showcaseBase/ronaldo-penalties/final.mp4'),
          )
          ..setLooping(true)
          ..setVolume(0)
          ..initialize().then((_) {
            _video.play();
            if (mounted) setState(() {});
          });
  }

  @override
  void dispose() {
    _video.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AppCard(
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Row(
          children: [
            BrandMark(compact: true),
            SizedBox(width: 10),
            Text(
              'BanterClips Studio',
              style: TextStyle(fontWeight: FontWeight.w700),
            ),
          ],
        ),
        const SizedBox(height: 18),
        const Text(
          'YOUR SPORTS TAKE',
          style: TextStyle(
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1,
            color: AppColors.muted2,
          ),
        ),
        const SizedBox(height: 8),
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: AppColors.panel,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(color: AppColors.border),
          ),
          child: const Text("Lakers won't make the playoffs."),
        ),
        const SizedBox(height: 14),
        if (_video.value.isInitialized) ...[
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(aspectRatio: 9 / 16, child: VideoPlayer(_video)),
          ),
          const SizedBox(height: 14),
        ],
        for (final text in [
          'Viral script written',
          'Commentator voice',
          'Animated captions',
        ])
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: 1),
            duration: const Duration(milliseconds: 900),
            builder: (context, value, child) => Opacity(
              opacity: value,
              child: Transform.translate(
                offset: Offset(0, 8 * (1 - value)),
                child: child,
              ),
            ),
            child: Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                children: [
                  const Icon(
                    Icons.check_circle,
                    size: 17,
                    color: AppColors.green,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    text,
                    style: const TextStyle(
                      fontSize: 13,
                      color: AppColors.muted,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    ),
  );
}

class _TrustStrip extends StatelessWidget {
  const _TrustStrip();
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
    color: AppColors.sidebar,
    child: const Column(
      children: [
        Text(
          'Trusted by sports creators, podcasters, YouTubers & media teams',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, color: AppColors.muted),
        ),
        SizedBox(height: 16),
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 18,
          runSpacing: 10,
          children: [
            Text('HOOPSDAILY', style: _trustStyle),
            Text('THE PODCAST', style: _trustStyle),
            Text('GRIDIRON+', style: _trustStyle),
            Text('FOOTYWORLD', style: _trustStyle),
            Text('COURTSIDE', style: _trustStyle),
          ],
        ),
      ],
    ),
  );
}

const _trustStyle = TextStyle(
  fontSize: 11,
  fontWeight: FontWeight.w800,
  letterSpacing: .6,
  color: AppColors.muted2,
);

class _HowItWorks extends StatefulWidget {
  const _HowItWorks();
  @override
  State<_HowItWorks> createState() => _HowItWorksState();
}

class _HowItWorksState extends State<_HowItWorks> {
  static const take = "Wemby's so tall the Spurs just pass him the roof.";
  static const stages = [
    'Writing your script',
    'Casting Victor Wembanyama',
    'Designing scene 1 of 2',
    'Bringing scene 1 to life',
    'Adding captions',
  ];
  Timer? _timer;
  int _tick = 0;
  late final VideoPlayerController _clip;

  @override
  void initState() {
    super.initState();
    _clip =
        VideoPlayerController.networkUrl(
            Uri.parse('$_showcaseBase/ronaldo-penalties/final.mp4'),
          )
          ..setLooping(true)
          ..setVolume(0)
          ..initialize().then((_) {
            if (mounted) setState(() {});
          });
    _timer = Timer.periodic(const Duration(milliseconds: 90), (_) {
      if (mounted) setState(() => _tick = (_tick + 1) % 170);
    });
  }

  @override
  void dispose() {
    _timer?.cancel();
    _clip.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 38, 20, 22),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.center,
      children: [
        const Text(
          'How it works',
          style: TextStyle(
            fontSize: 30,
            fontWeight: FontWeight.w800,
            color: AppColors.text,
          ),
        ),
        const SizedBox(height: 18),
        _step(
          '1',
          'Type your take',
          _typing(),
          'One sentence. That’s the whole input.',
        ),
        _step(
          '2',
          'The AI builds it',
          _pipeline(),
          'The real production pipeline, step by step.',
        ),
        _step(
          '3',
          'Publish or download',
          _result(),
          '9:16 · captions burned in · ready to post.',
        ),
      ],
    ),
  );

  Widget _step(String n, String title, Widget visual, String note) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: AppCard(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              gradient: AppColors.gradient,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Center(
              child: Text(
                n,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  color: AppColors.onGradient,
                ),
              ),
            ),
          ),
          const SizedBox(width: 13),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontWeight: FontWeight.w700,
                    color: AppColors.text,
                  ),
                ),
                const SizedBox(height: 6),
                visual,
                const SizedBox(height: 5),
                Text(
                  note,
                  style: const TextStyle(
                    fontSize: 11.5,
                    color: AppColors.muted2,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );

  Widget _typing() {
    final count = _tick.clamp(0, take.length);
    return Container(
      height: 120,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.panel,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        '${take.substring(0, count)}${_tick.isEven ? '|' : ''}',
        style: const TextStyle(
          fontSize: 17,
          height: 1.4,
          fontWeight: FontWeight.w600,
        ),
      ),
    );
  }

  Widget _pipeline() {
    final active = ((_tick - 58) ~/ 12).clamp(-1, stages.length);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.panel,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        children: [
          for (var i = 0; i < stages.length; i++)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 5),
              child: Row(
                children: [
                  Icon(
                    i < active
                        ? Icons.check_circle
                        : i == active
                        ? Icons.sync
                        : Icons.circle_outlined,
                    size: 17,
                    color: i <= active ? AppColors.cyan : AppColors.muted2,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      stages[i],
                      style: TextStyle(
                        fontSize: 12.5,
                        fontWeight: i == active
                            ? FontWeight.w700
                            : FontWeight.w500,
                        color: i <= active ? AppColors.text : AppColors.muted2,
                      ),
                    ),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _result() {
    final ready = _tick > 118;
    if (ready && _clip.value.isInitialized && !_clip.value.isPlaying) {
      _clip.play();
    }
    if (!ready && _clip.value.isPlaying) _clip.pause();
    return AspectRatio(
      aspectRatio: 4 / 5,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: AnimatedSwitcher(
          duration: const Duration(milliseconds: 450),
          child: ready && _clip.value.isInitialized
              ? FittedBox(
                  key: const ValueKey('clip'),
                  fit: BoxFit.cover,
                  child: SizedBox(
                    width: _clip.value.size.width,
                    height: _clip.value.size.height,
                    child: VideoPlayer(_clip),
                  ),
                )
              : Container(
                  key: const ValueKey('waiting'),
                  color: AppColors.panel,
                  alignment: Alignment.center,
                  child: const Text(
                    'waiting for the render…',
                    style: TextStyle(color: AppColors.muted2),
                  ),
                ),
        ),
      ),
    );
  }
}

class _Testimonials extends StatelessWidget {
  const _Testimonials();
  static const quotes = [
    (
      '“Two minutes from a group-chat argument to something I can actually post.”',
      'Marcus D.',
      'Sports YouTuber',
    ),
    (
      '“It gets the joke. I type a petty take and it comes back sharper than I wrote it.”',
      'Tasha R.',
      'TikTok creator',
    ),
    (
      '“A take goes up while the argument is still happening—which is the only time anyone cares.”',
      'Leo P.',
      'Sports media producer',
    ),
  ];
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 34, 20, 10),
    child: Column(
      children: [
        for (final q in quotes)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: AppCard(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    q.$1,
                    style: const TextStyle(
                      fontSize: 15,
                      height: 1.5,
                      color: AppColors.text,
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    q.$2,
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
                  Text(
                    q.$3,
                    style: const TextStyle(
                      fontSize: 11.5,
                      color: AppColors.muted2,
                    ),
                  ),
                ],
              ),
            ),
          ),
      ],
    ),
  );
}

class _Stats extends StatelessWidget {
  const _Stats();
  static const stats = [
    ('720 × 1280', 'Vertical H.264'),
    ('~2 minutes', 'Take to finished clip'),
    ('Real players', 'Recognisable kits'),
    ('Captions burned in', 'No editor needed'),
  ];
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.all(20),
    child: GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      itemCount: stats.length,
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.45,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemBuilder: (_, i) => AppCard(
        padding: const EdgeInsets.all(14),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              stats[i].$1,
              textAlign: TextAlign.center,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w800,
                color: AppColors.text,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              stats[i].$2,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 10.5, color: AppColors.muted2),
            ),
          ],
        ),
      ),
    ),
  );
}

class _FinalCta extends StatelessWidget {
  const _FinalCta();
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 12, 20, 40),
    child: Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [AppColors.cyanWash(.18), AppColors.greenWash(.16)],
        ),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppColors.border),
      ),
      child: Column(
        children: [
          const Text(
            'Ready to make sports content 10× faster?',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 25,
              fontWeight: FontWeight.w800,
              color: AppColors.text,
            ),
          ),
          const SizedBox(height: 18),
          GradButton(
            label: 'Start Free →',
            onPressed: () => context.go('/sign-in'),
          ),
        ],
      ),
    ),
  );
}

class PricingScreen extends ConsumerWidget {
  const PricingScreen({super.key, this.embedded = false});
  final bool embedded;
  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: embedded
        ? AppBar(title: const Text('Pricing'))
        : const PublicHeader(),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 38, 20, 32),
      children: [
        const Text(
          'Simple, creator-friendly pricing',
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 34,
            fontWeight: FontWeight.w800,
            letterSpacing: -.8,
          ),
        ),
        const SizedBox(height: 10),
        const Text(
          'Turn a written sports take into a finished 9:16 AI video — voiceover, animated captions, one-click publish to Instagram & TikTok. Start free, no credit card.',
          textAlign: TextAlign.center,
          style: TextStyle(color: AppColors.muted, height: 1.5),
        ),
        const SizedBox(height: 28),
        _Plan(
          name: 'Free',
          price: r'$0',
          note: 'Your clips, published everywhere.',
          features: const [
            '60 welcome credits — your first video on us',
            'One-click publish to Instagram & TikTok',
            'Funny · Savage · Hype tones',
            'Free retries — failures never count',
            '— 720p HD only',
            '— Publishes with BanterClips watermark',
            '— No downloads',
          ],
          onTap: () =>
              embedded ? context.go('/studio') : context.go('/sign-in'),
        ),
        const SizedBox(height: 16),
        _Plan(
          name: 'Creator',
          price: r'$19',
          note: 'For creators posting every week.',
          popular: true,
          features: const [
            '150 credits added every month',
            'Full HD 1080p quality',
            'Download in HD — no watermark',
            'Publish without the watermark',
            'Priority render queue',
            'First access to new platforms',
            'Everything in Free',
          ],
          onTap: () => embedded
              ? showUpgradeSheet(context, reason: UpgradeReason.limit)
              : context.go('/sign-in'),
        ),
        const SizedBox(height: 18),
        const Text(
          'Prices are introductory and may change after beta. The AI-parody disclosure stays on every video on every plan. Only successful videos use credits — failures are refunded. Cancel anytime — your videos are never deleted.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 12, height: 1.55, color: AppColors.muted2),
        ),
      ],
    ),
  );
}

class _Plan extends StatelessWidget {
  const _Plan({
    required this.name,
    required this.price,
    required this.note,
    required this.features,
    required this.onTap,
    this.popular = false,
  });
  final String name, price, note;
  final List<String> features;
  final VoidCallback onTap;
  final bool popular;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(22),
    decoration: BoxDecoration(
      color: AppColors.surface,
      borderRadius: BorderRadius.circular(20),
      border: Border.all(color: popular ? AppColors.cyan : AppColors.border),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (popular) const _Eyebrow('POPULAR'),
        if (popular) const SizedBox(height: 8),
        Text(
          name,
          style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              price,
              style: const TextStyle(fontSize: 38, fontWeight: FontWeight.w800),
            ),
            const Padding(
              padding: EdgeInsets.only(bottom: 7),
              child: Text('/mo', style: TextStyle(color: AppColors.muted)),
            ),
          ],
        ),
        Text(note, style: const TextStyle(color: AppColors.muted)),
        const SizedBox(height: 18),
        for (final item in features)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Row(
              children: [
                Icon(
                  item.startsWith('—')
                      ? Icons.remove_rounded
                      : Icons.check_rounded,
                  size: 18,
                  color: item.startsWith('—')
                      ? AppColors.muted2
                      : AppColors.green,
                ),
                const SizedBox(width: 9),
                Expanded(
                  child: Text(
                    item.startsWith('— ') ? item.substring(2) : item,
                    style: TextStyle(
                      color: item.startsWith('—')
                          ? AppColors.muted2
                          : AppColors.text,
                    ),
                  ),
                ),
              ],
            ),
          ),
        const SizedBox(height: 10),
        if (popular)
          GradButton(label: 'Go Creator', onPressed: onTap)
        else
          GhostButton(label: 'Start free', onPressed: onTap),
      ],
    ),
  );
}

class ShowcaseScreen extends StatelessWidget {
  const ShowcaseScreen({super.key});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const PublicHeader(),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 34, 20, 32),
      children: [
        const Text(
          'Made with BanterClips',
          style: TextStyle(fontSize: 34, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          'Real AI-generated sports clips, each made from one written take.',
          style: TextStyle(color: AppColors.muted, height: 1.5),
        ),
        const SizedBox(height: 24),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: _clips.length,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            childAspectRatio: .56,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
          ),
          itemBuilder: (_, i) => ShowcaseCard(clip: _clips[i]),
        ),
      ],
    ),
  );
}

class ShowcaseCard extends StatelessWidget {
  const ShowcaseCard({super.key, required this.clip});
  final ({String slug, String sport, String take, String blurb}) clip;
  @override
  Widget build(BuildContext context) => GestureDetector(
    onTap: () => context.go('/showcase/${clip.slug}'),
    child: ClipRRect(
      borderRadius: BorderRadius.circular(16),
      child: Stack(
        fit: StackFit.expand,
        children: [
          CachedNetworkImage(
            imageUrl: _poster(clip.slug),
            fit: BoxFit.cover,
            placeholder: (_, __) => Container(color: AppColors.surface),
            errorWidget: (_, __, ___) => Container(
              decoration: BoxDecoration(
                gradient: AppColors.thumbFor(clip.slug),
              ),
            ),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Colors.transparent, Color(0xE6000000)],
              ),
            ),
          ),
          const Center(
            child: CircleAvatar(
              backgroundColor: Color(0xB3000000),
              child: Icon(Icons.play_arrow_rounded, color: Colors.white),
            ),
          ),
          Positioned(
            left: 12,
            right: 12,
            bottom: 12,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  clip.sport,
                  style: const TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    color: AppColors.cyan,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  clip.take,
                  maxLines: 3,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    fontSize: 12,
                    height: 1.25,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}

class ShowcaseClipScreen extends StatefulWidget {
  const ShowcaseClipScreen({super.key, required this.slug});
  final String slug;
  @override
  State<ShowcaseClipScreen> createState() => _ShowcaseClipScreenState();
}

class _ShowcaseClipScreenState extends State<ShowcaseClipScreen> {
  VideoPlayerController? controller;
  @override
  void initState() {
    super.initState();
    controller =
        VideoPlayerController.networkUrl(Uri.parse(_video(widget.slug)))
          ..initialize().then((_) {
            if (mounted) setState(() {});
          });
  }

  @override
  void dispose() {
    controller?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final clip = _clips.where((c) => c.slug == widget.slug).firstOrNull;
    if (clip == null) {
      return Scaffold(
        appBar: const PublicHeader(),
        body: const Center(child: Text('Clip not found.')),
      );
    }
    final ready = controller?.value.isInitialized == true;
    return Scaffold(
      appBar: const PublicHeader(),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          AspectRatio(
            aspectRatio: 9 / 16,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(18),
              child: ready
                  ? Stack(
                      fit: StackFit.expand,
                      children: [
                        VideoPlayer(controller!),
                        Center(
                          child: IconButton.filled(
                            iconSize: 36,
                            onPressed: () => setState(() {
                              controller!.value.isPlaying
                                  ? controller!.pause()
                                  : controller!.play();
                            }),
                            icon: Icon(
                              controller!.value.isPlaying
                                  ? Icons.pause
                                  : Icons.play_arrow,
                            ),
                          ),
                        ),
                      ],
                    )
                  : CachedNetworkImage(
                      imageUrl: _poster(clip.slug),
                      fit: BoxFit.cover,
                    ),
            ),
          ),
          const SizedBox(height: 22),
          Text(
            clip.sport.toUpperCase(),
            style: const TextStyle(
              fontSize: 11,
              fontWeight: FontWeight.w800,
              letterSpacing: 1,
              color: AppColors.cyan,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            clip.take,
            style: const TextStyle(
              fontSize: 26,
              height: 1.18,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            clip.blurb,
            style: const TextStyle(color: AppColors.muted, height: 1.55),
          ),
          const SizedBox(height: 22),
          GradButton(
            label: 'Make your own →',
            onPressed: () => context.go('/sign-in'),
          ),
        ],
      ),
    );
  }
}

class LegalScreen extends StatelessWidget {
  const LegalScreen({super.key, required this.terms});
  final bool terms;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const PublicHeader(),
    body: ListView(
      padding: const EdgeInsets.fromLTRB(20, 32, 20, 48),
      children: [
        Text(
          terms ? 'Terms of Service' : 'Privacy Policy',
          style: const TextStyle(fontSize: 32, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          'Last updated September 2026',
          style: TextStyle(color: AppColors.muted2),
        ),
        const SizedBox(height: 26),
        for (final section in (terms ? _terms : _privacy)) ...[
          Text(
            section.$1,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          Text(
            section.$2,
            style: const TextStyle(color: AppColors.muted, height: 1.6),
          ),
          const SizedBox(height: 22),
        ],
      ],
    ),
  );
}

class ResetPasswordScreen extends ConsumerStatefulWidget {
  const ResetPasswordScreen({super.key});
  @override
  ConsumerState<ResetPasswordScreen> createState() =>
      _ResetPasswordScreenState();
}

class _ResetPasswordScreenState extends ConsumerState<ResetPasswordScreen> {
  final password = TextEditingController();
  final confirm = TextEditingController();
  bool saving = false;
  String? error;
  bool complete = false;

  @override
  void dispose() {
    password.dispose();
    confirm.dispose();
    super.dispose();
  }

  Future<void> save() async {
    if (password.text.length < 8) {
      setState(() => error = 'Use at least 8 characters.');
      return;
    }
    if (password.text != confirm.text) {
      setState(() => error = 'Passwords do not match.');
      return;
    }
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await ref.read(appStateProvider.notifier).updatePassword(password.text);
      if (mounted) setState(() => complete = true);
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: const PublicHeader(),
    body: Center(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 440),
          child: AppCard(
            child: complete
                ? Column(
                    children: [
                      const Icon(
                        Icons.check_circle_rounded,
                        size: 52,
                        color: AppColors.green,
                      ),
                      const SizedBox(height: 16),
                      const Text(
                        'Password updated',
                        style: TextStyle(
                          fontSize: 24,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Your new password is ready to use.',
                        style: TextStyle(color: AppColors.muted),
                      ),
                      const SizedBox(height: 20),
                      GradButton(
                        label: 'Continue',
                        onPressed: () => context.go('/studio'),
                      ),
                    ],
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const BrandMark(),
                      const SizedBox(height: 24),
                      const Text(
                        'Choose a new password',
                        style: TextStyle(
                          fontSize: 25,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                      const SizedBox(height: 8),
                      const Text(
                        'Enter your new BanterClips password below.',
                        style: TextStyle(color: AppColors.muted),
                      ),
                      const SizedBox(height: 20),
                      TextField(
                        controller: password,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'New password',
                        ),
                      ),
                      const SizedBox(height: 12),
                      TextField(
                        controller: confirm,
                        obscureText: true,
                        decoration: const InputDecoration(
                          labelText: 'Confirm password',
                        ),
                      ),
                      if (error != null) ...[
                        const SizedBox(height: 12),
                        Text(
                          error!,
                          style: const TextStyle(color: AppColors.error),
                        ),
                      ],
                      const SizedBox(height: 18),
                      GradButton(
                        label: saving ? 'Saving…' : 'Update password',
                        onPressed: saving ? null : save,
                      ),
                    ],
                  ),
          ),
        ),
      ),
    ),
  );
}

const _privacy = [
  (
    'Information we collect',
    'We collect account details, preferences, submitted sports takes, generated media, usage events and connected social-account information needed to provide the service.',
  ),
  (
    'How we use information',
    'We use this information to authenticate you, generate and deliver clips, operate billing, improve reliability and prevent abuse.',
  ),
  (
    'Storage and sharing',
    'Service providers such as Supabase, generation providers, Stripe and connected publishing platforms process only the data needed for their function.',
  ),
  (
    'Your choices',
    'You may disconnect social accounts, request deletion or contact support about access and correction.',
  ),
];
const _terms = [
  (
    'The service',
    'BanterClips turns written sports opinions into AI-generated parody videos. Generated output can contain errors and must be reviewed before publishing.',
  ),
  (
    'Plans and credits',
    r'Free includes 60 welcome credits. Creator costs $19 per month and adds 150 monthly credits, 1080p output and watermark-free downloads.',
  ),
  (
    'Your responsibilities',
    'You are responsible for your takes, generated clips and publication choices, including compliance with platform rules and applicable law.',
  ),
  (
    'Subscriptions',
    'Subscriptions renew until cancelled. Access continues through the paid billing period after cancellation.',
  ),
];

class _LandingSection extends StatelessWidget {
  const _LandingSection({
    required this.eyebrow,
    required this.title,
    required this.children,
  });
  final String eyebrow, title;
  final List<Widget> children;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.fromLTRB(20, 42, 20, 20),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _Eyebrow(eyebrow),
        const SizedBox(height: 10),
        Text(
          title,
          textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 18),
        ...children,
      ],
    ),
  );
}

class _Feature extends StatefulWidget {
  const _Feature({required this.icon, required this.title, required this.text});
  final IconData icon;
  final String title, text;
  @override
  State<_Feature> createState() => _FeatureState();
}

class _FeatureState extends State<_Feature> {
  Timer? timer;
  int tick = 0;
  @override
  void initState() {
    super.initState();
    timer = Timer.periodic(const Duration(milliseconds: 240), (_) {
      if (mounted) setState(() => tick++);
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 12),
    child: AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          _visual(),
          const SizedBox(height: 16),
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(widget.icon, color: AppColors.cyan),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      widget.title,
                      style: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    const SizedBox(height: 5),
                    Text(
                      widget.text,
                      style: const TextStyle(
                        fontSize: 13,
                        color: AppColors.muted,
                        height: 1.45,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    ),
  );

  Widget _visual() {
    if (widget.title == 'AI Video Generator') {
      return ClipRRect(
        borderRadius: BorderRadius.circular(12),
        child: SizedBox(
          height: 150,
          child: Stack(
            fit: StackFit.expand,
            children: [
              CachedNetworkImage(
                imageUrl: '$_showcaseBase/ronaldo-penalties/poster.jpg',
                fit: BoxFit.cover,
                alignment: const Alignment(0, -.35),
              ),
              const Positioned(
                right: 10,
                bottom: 8,
                child: Text(
                  '720 × 1280 · 9:16',
                  style: TextStyle(
                    fontSize: 10,
                    fontWeight: FontWeight.w700,
                    color: Colors.white,
                  ),
                ),
              ),
            ],
          ),
        ),
      );
    }
    if (widget.title == 'AI Voiceovers') {
      return _gradientFrame(
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            for (var i = 0; i < 12; i++)
              AnimatedContainer(
                duration: const Duration(milliseconds: 210),
                margin: const EdgeInsets.symmetric(horizontal: 2),
                width: 4,
                height: 16 + ((tick + i * 3) % 7) * 6,
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(3),
                ),
              ),
          ],
        ),
      );
    }
    if (widget.title == 'Animated Captions') {
      const words = ['Nothing', 'gets', 'past', 'me.'];
      return _gradientFrame(
        Wrap(
          alignment: WrapAlignment.center,
          spacing: 7,
          children: [
            for (var i = 0; i < words.length; i++)
              AnimatedScale(
                duration: const Duration(milliseconds: 180),
                scale: tick % words.length == i ? 1.25 : 1,
                child: Text(
                  words[i],
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w800,
                    color: Colors.white,
                  ),
                ),
              ),
          ],
        ),
      );
    }
    if (widget.title == 'One-Click Publishing') {
      return _gradientFrame(
        AnimatedSlide(
          duration: const Duration(milliseconds: 700),
          offset: Offset(0, tick.isEven ? -.18 : .18),
          child: const Icon(Icons.send_rounded, size: 58, color: Colors.white),
        ),
      );
    }
    const tones = ['Funny', 'Savage', 'Hype', 'Bold'];
    return _gradientFrame(
      Wrap(
        alignment: WrapAlignment.center,
        spacing: 8,
        runSpacing: 8,
        children: [
          for (var i = 0; i < tones.length; i++)
            AnimatedContainer(
              duration: const Duration(milliseconds: 250),
              padding: const EdgeInsets.symmetric(horizontal: 13, vertical: 7),
              decoration: BoxDecoration(
                color: tick % tones.length == i
                    ? Colors.white30
                    : Colors.white12,
                borderRadius: BorderRadius.circular(30),
                border: Border.all(
                  color: tick % tones.length == i
                      ? Colors.white
                      : Colors.white38,
                ),
              ),
              child: Text(
                tones[i],
                style: const TextStyle(
                  color: Colors.white,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _gradientFrame(Widget child) => Container(
    height: 150,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      gradient: AppColors.gradient,
      borderRadius: BorderRadius.circular(12),
    ),
    child: child,
  );
}

class _Eyebrow extends StatelessWidget {
  const _Eyebrow(this.text);
  final String text;
  @override
  Widget build(BuildContext context) => Text(
    text,
    style: const TextStyle(
      fontSize: 10.5,
      fontWeight: FontWeight.w800,
      letterSpacing: 1.2,
      color: AppColors.cyan,
    ),
  );
}

class _Footer extends StatelessWidget {
  const _Footer();
  @override
  Widget build(BuildContext context) => Container(
    color: AppColors.sidebar,
    padding: const EdgeInsets.fromLTRB(20, 28, 20, 36),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const BrandMark(),
        const SizedBox(height: 12),
        const Text(
          'Every sports opinion deserves a viral video.',
          style: TextStyle(color: AppColors.muted),
        ),
        const SizedBox(height: 18),
        Wrap(
          spacing: 18,
          children: [
            TextButton(
              onPressed: () => context.go('/privacy'),
              child: const Text('Privacy'),
            ),
            TextButton(
              onPressed: () => context.go('/terms'),
              child: const Text('Terms'),
            ),
            TextButton(
              onPressed: () => context.go('/pricing'),
              child: const Text('Pricing'),
            ),
          ],
        ),
      ],
    ),
  );
}
