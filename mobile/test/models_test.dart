import 'package:banterclips/models/clip.dart';
import 'package:banterclips/models/script.dart';
import 'package:banterclips/models/user.dart';
import 'package:flutter_test/flutter_test.dart';

/// Tests for the logic that would otherwise break silently: JSON parsing,
/// the derived clip states every screen switches on, the resolution label
/// the UI advertises, and the sparse script patch sent back to the API.
///
/// The resolution cases are ported from `frontend/src/lib/format.js`, whose
/// own comment records that four hardcoded "1080 × 1920" labels quietly
/// became false advertising once. Two clients, one arithmetic.
void main() {
  group('Clip.resolutionLabel', () {
    test('720p matches the web constant', () {
      expect(_clip(resolution: '720p').resolutionLabel, '720 × 1280 · 9:16');
    });

    test('1080p floors the height to an even number, as the backend does', () {
      // 1080 * 16 / 9 = 1920 exactly, so this one is easy — but it is the
      // label that went wrong on the web, so it is pinned here.
      expect(_clip(resolution: '1080p').resolutionLabel, '1080 × 1920 · 9:16');
    });

    test('an odd-height width is floored to even, never rounded up', () {
      // 722 * 16 / 9 = 1283.55… → floor(641.7)*2 = 1282, not 1284.
      expect(_clip(resolution: '722p').resolutionLabel, '722 × 1282 · 9:16');
    });

    test('an unparseable resolution falls back rather than printing garbage', () {
      expect(_clip(resolution: '').resolutionLabel, '720 × 1280 · 9:16');
      expect(_clip(resolution: 'auto').resolutionLabel, '720 × 1280 · 9:16');
    });
  });

  group('Clip state derivation', () {
    test('a stage status counts as in flight, not as failed', () {
      final clip = _clip(status: 'animating_scenes');
      expect(clip.inFlight, isTrue);
      expect(clip.isReady, isFalse);
      expect(clip.hasFailed, isFalse);
      expect(clip.statusLabel, 'Animating scenes…');
    });

    test('script_ready is NOT in flight — it is waiting on the user', () {
      // This is the money gate: treating it as in-flight would leave the
      // screen polling forever on a job that has deliberately stopped.
      final clip = Clip.fromJson({
        ..._json(status: 'script_ready'),
        'script': {'title': 'x', 'scenes': []},
      });
      expect(clip.awaitingScript, isTrue);
      expect(clip.inFlight, isFalse);
    });

    test('script_ready with no script body is not a valid gate', () {
      final clip = _clip(status: 'script_ready');
      expect(clip.awaitingScript, isFalse);
    });

    test('ready without a video URL is "preparing", never a failure', () {
      final clip = _clip(status: 'ready');
      expect(clip.isReady, isTrue);
      expect(clip.isPreparing, isTrue);
      expect(clip.hasFailed, isFalse);
    });

    test('publish state is read from the publishes list', () {
      final clip = Clip.fromJson({
        ..._json(status: 'ready'),
        'video_url': 'https://example.com/a.mp4',
        'publishes': [
          {
            'id': 'p1',
            'clip_id': 'c1',
            'social_account_id': 's1',
            'caption': '',
            'status': 'published',
            'external_url': 'https://instagram.com/reel/1',
          },
        ],
      });
      expect(clip.isPublished, isTrue);
      expect(clip.isPublishing, isFalse);
      expect(clip.publishedPost?.externalUrl, 'https://instagram.com/reel/1');
    });
  });

  group('Clip.fromJson tolerance', () {
    test('survives a response with only the required fields', () {
      final clip = Clip.fromJson({
        'id': 'abc',
        'take': 'Messi is still the GOAT.',
        'sport': 'Soccer',
        'tone': 'Bold',
        'status': 'queued',
      });
      expect(clip.durationTarget, 15);
      expect(clip.resolution, '720p');
      expect(clip.publishes, isEmpty);
      expect(clip.script, isNull);
    });

    test('download filename matches the one the backend sends', () {
      final clip = _clip(id: '0f8a3b21-dead-beef-0000-111122223333', sport: 'NBA');
      expect(clip.downloadFilename, 'banterclips-nba-0f8a3b21.mp4');
    });
  });

  group('Script.diffAgainst', () {
    final original = Script.fromJson({
      'title': 'Original',
      'scenes': [
        {'seconds': 4, 'line': 'One', 'action': 'A'},
        {'seconds': 4, 'line': 'Two', 'action': 'B'},
      ],
    });

    test('an untouched draft produces no patch at all', () {
      expect(original.withScenes([...original.scenes]).diffAgainst(original), isEmpty);
    });

    test('only the changed field of the changed shot is sent', () {
      final edited = original.withScenes([
        original.scenes[0],
        original.scenes[1].copyWith(line: 'Two, but funnier'),
      ]);
      final patch = edited.diffAgainst(original);

      expect(patch, hasLength(1));
      expect(patch.single['index'], 1);
      expect(patch.single['line'], 'Two, but funnier');
      // Sending the unchanged action back would re-trim a line the server
      // has already fitted, and mark the whole script edited.
      expect(patch.single.containsKey('action'), isFalse);
    });

    test('clearing a line is a real edit — a silent shot is a choice', () {
      final edited = original.withScenes([
        original.scenes[0].copyWith(line: ''),
        original.scenes[1],
      ]);
      expect(edited.diffAgainst(original).single['line'], '');
    });
  });

  group('Scene.wordBudget', () {
    test('scales with the shot length', () {
      expect(const Scene(seconds: 4).wordBudget, 8);
      expect(const Scene(seconds: 10).wordBudget, 22);
    });

    test('never drops below two words, however short the shot', () {
      expect(const Scene(seconds: 0.5).wordBudget, 2);
    });
  });

  group('Usage gating', () {
    test('the unknown default is pessimistic — never unlock by accident', () {
      expect(Usage.unknown.canDownload, isFalse);
      expect(Usage.unknown.watermarked, isTrue);
    });

    test('fraction is clamped so a bad server count cannot overflow the bar', () {
      const over = Usage(
        plan: 'free',
        used: 9,
        limit: 5,
        left: 0,
        canDownload: false,
        watermarked: true,
      );
      expect(over.fraction, 1.0);
    });
  });
}

Map<String, dynamic> _json({String status = 'ready'}) => {
      'id': 'c1',
      'take': 'A take that is long enough.',
      'sport': 'NBA',
      'tone': 'Funny',
      'status': status,
    };

Clip _clip({
  String id = 'c1',
  String status = 'ready',
  String sport = 'NBA',
  String resolution = '720p',
}) =>
    Clip.fromJson({
      ..._json(status: status),
      'id': id,
      'sport': sport,
      'resolution': resolution,
    });
