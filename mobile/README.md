# BanterClips mobile app

Flutter client for Android and iOS. Same product as the website, same
accounts, same clips — a second client of the FastAPI backend, not a second
product. Nothing user-facing is faked: every screen reads from
`api.banterclips.com` exactly as `frontend/` does.

Companion documents: [`../MOBILE-ROADMAP.html`](../MOBILE-ROADMAP.html) (the
plan this implements) and [`../BRD.md`](../BRD.md) (the business rules).

## Tech stack

| Layer | Choice | Replaces (web) |
|---|---|---|
| Framework | Flutter 3.32 · Dart 3.8 | React 18 |
| Routing | `go_router` — one `redirect` is the whole auth gate | `react-router-dom` |
| State | `flutter_riverpod` — `AppStateNotifier` mirrors `AppContext.jsx` | React Context |
| HTTP | `dio` with token + error interceptors | `fetch` in `lib/api.js` |
| Auth | `supabase_flutter` → token exchanged for an API session | `@supabase/supabase-js` |
| Token storage | `flutter_secure_storage` (Keychain / Keystore) | `localStorage` |
| Video | `video_player` + `chewie`, full-bleed 9:16 | `<video>` |
| Sharing | `share_plus` — the native share sheet | (no equivalent) |
| OAuth sheet | `flutter_web_auth_2` (ASWebAuthenticationSession / Custom Tabs) | full-page redirect |

Models are hand-written with `fromJson` factories rather than generated with
`freezed`. The shapes are small and stable, and a readable `fromJson` beats
one that needs `build_runner` re-run on every API change.

## Local setup

```bash
flutter pub get

# against the backend on this machine
flutter run \
  --dart-define=API_URL=http://10.0.2.2:8000 \
  --dart-define=SUPABASE_URL=https://taphbakizdagamimbhjh.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=<anon key — infra/supabase.md>

# against production
flutter run
```

For the existing BanterClips Supabase project, keep the client-safe URL and
publishable key in the git-ignored `config/supabase.local.json`, then run:

```bash
flutter run --dart-define-from-file=config/supabase.local.json
```

**`10.0.2.2`, not `localhost`.** That is how the Android emulator reaches the
host machine; inside the emulator `localhost` is the emulator itself. On a
physical device use your machine's LAN IP, and make sure the backend's
`CORS_ORIGINS` does not matter here — native clients are not subject to CORS.

## Environment

Flutter's `.env` equivalent is compile-time: `--dart-define`, read back
through `String.fromEnvironment` in [`lib/app/env.dart`](lib/app/env.dart).

| Define | Default | Notes |
|---|---|---|
| `API_URL` | `https://api.banterclips.com` | so a plain `flutter build` ships something that works |
| `SUPABASE_URL` | *(empty)* | same project as the web app |
| `SUPABASE_ANON_KEY` | *(empty)* | publishable by design |

With **both** Supabase values empty the app falls back to the backend's dev
magic-link (`/auth/request-link`), which only exists when the backend runs
with `DEV_MODE=true`. That is the fully-offline development path.

## Project structure

Feature-first, which scales past a dozen screens better than type-first.

```
lib/
├── main.dart          entry point, Supabase init, orientation
├── app/               env · router (the auth gate) · root widget
├── theme/             colors · typography · app_theme
├── api/               client · errors · token_store
├── models/            user · clip · script · social
├── state/             app_state.dart — the AppContext.jsx port
├── widgets/           the component catalog (buttons, surfaces, states)
└── features/
    ├── auth/          sign in · sign up · reset
    ├── onboarding/    four skippable steps
    ├── shell/         bottom tab bar
    ├── studio/        take → script review → progress → result
    ├── clips/         library · player · publish sheet
    └── account/       plan · socials · preferences · legal
```

## What ships, and what deliberately does not

| Web screen | Here | Why |
|---|---|---|
| Sign in · Reset | ✅ | nothing works without it |
| Onboarding | ✅ | four steps, all skippable |
| Studio (all phases) | ✅ | split across `/studio` and `/clip/:id` |
| Clips | ✅ | list, play, publish, share, delete |
| Account | ✅ | usage, plan, Instagram, preferences, legal |
| Pricing | ↗ web | store-billing rules — see below |
| Privacy · Terms | ↗ web | both stores need reachable links; rebuilding buys nothing |
| Landing · Showcase | ❌ | marketing and SEO surfaces; an installed user has converted |
| `admin/*` | ❌ | ops tooling, desktop browser forever |

### Billing runs through the stores

Creator at $9.99/month is a digital subscription consumed inside the app, so
Apple (Guideline 3.1.1) and Google both require it to go through their
billing — a Stripe Checkout page opened from the app is a straightforward
rejection. That costs 15–30% on top of margins `../UNIT-ECONOMICS.md` already
calls thin, so the mobile price is worth revisiting.

**The client never decides who is a Creator.** A completed purchase is only a
signal to go and ask the server:

```
buy -> store sheet -> purchase stream -> POST /billing/mobile/verify
    -> server asks Apple/Google -> server writes users.plan
    -> app refetches /me -> completePurchase()
```

That last step is not optional: an unacknowledged Android purchase is
automatically refunded after three days.

Client half: [`lib/features/account/purchases.dart`](lib/features/account/purchases.dart).
Server half: `backend/app/services/store_billing.py` (the App Store Server API
and the Play Developer API) behind `POST /billing/mobile/verify`. Configure it
with the `APPLE_*` and `GOOGLE_PLAY_*` variables in `backend/.env.example`;
with those empty the endpoint answers 503 and the paywall falls back to
sending the user to the website.

Three rules the implementation encodes, worth not undoing:

* **One receipt, one account.** `purchase_token` is unique across the whole
  `store_subscriptions` table, so a receipt passed to a friend hits the
  constraint instead of granting them Creator.
* **A store outage never downgrades a paying customer.** If Apple cannot be
  reached, the entitlement is left exactly as it was.
* **Expiry is self-healing.** The store's `expires_at` is stored, and
  `/me/usage` re-checks only once it has actually passed — so a lapsed
  subscription downgrades even though server-to-server notifications (Google
  RTDN, Apple ASSN) are not wired up yet. Those are the follow-up: they make
  a cancellation visible in minutes rather than at the next read.

Cancellation is **not** possible from inside the app — neither store exposes
an API for it. `POST /billing/cancel` returns `409 cancel_in_store` for a
store subscription, and Account deep-links to the right settings screen.
Setting our own flag instead would be worse than useless: the customer would
see "cancelled" here and keep being charged.

## Long jobs and the phone lifecycle

A browser tab can poll forever. A phone cannot: iOS suspends the process
seconds after the user leaves and Android kills it under memory pressure,
while a render takes minutes. So:

* `ClipScreen` polls every **2.5 s**, `ClipsScreen` every **3 s** (the web
  uses 0.9 s and 1.5 s), and only while something is actually in flight.
* Both implement `WidgetsBindingObserver` and **stop on background, refetch
  once on resume**. A timer left running is a battery complaint, not a
  feature.
* The copy tells the truth: leave the app, the render carries on server-side,
  and it is waiting in My Clips.

The real fix is a push notification when the worker finishes — that needs
`POST /me/devices`, a Firebase project, and a hook in `app/worker.py`. It is
v2, on purpose.

## Backend change still required: Instagram OAuth

**This is the one thing that is not finished, and it is a backend change, not
a Flutter one.**

`GET /socials/instagram/oauth-url` mints a state JWT holding a `next` path
and rejects anything not starting with `/`:

```python
# backend/app/routers/socials.py
"next": next if next.startswith("/") else "/account",
```

Correct for a website; wrong for an app, because a phone has no browser tab
to return to. The app already asks for `banterclips://oauth/instagram`, the
scheme is registered on both platforms, and `flutter_web_auth_2` is wired to
catch it. Until the backend allow-lists that exact URI, the consent flow ends
on the website instead of back in the app — the account still connects, and
pulling to refresh Account picks it up, but the hand-back is ugly.

The fix, both in `oauth-url` and wherever the callback redirects:

```python
MOBILE_RETURN = "banterclips://oauth/instagram"

def _safe_next(next: str) -> str:
    # Exactly one non-web destination is allowed, matched in full. Do NOT
    # relax this to "any custom scheme" — that is an open-redirect hole.
    if next == MOBILE_RETURN:
        return next
    return next if next.startswith("/") else "/account"
```

Then add `banterclips://oauth/instagram` to the Meta app's valid OAuth
redirect list, alongside the web one.

## Before the first store submission

Ordered by how expensive they get if left late.

1. **Create the subscription product** in App Store Connect and the Play
   Console, with the id `creator_monthly` in both. The same string on both
   stores is what lets the server verify a receipt without caring where it
   came from. Until it exists the paywall shows its "not available from the
   store on this build yet" state rather than a dead button.
2. **Register the Google Play account ($25).** New accounts must run a closed
   test with 12 testers for 14 days before public release. Start that clock
   early; it runs in the background while you build.
3. **Back up the Android upload keystore** somewhere outside the repo. Lose
   it and that Play listing can never be updated again. It is gitignored.
4. **Google sign-in needs its own OAuth clients** — an Android client keyed to
   both your debug *and release* SHA-1 fingerprints, and an iOS client keyed
   to the bundle id. Neither reuses the web client. Forgetting the release
   SHA-1 is the classic failure: it works all through testing and fails for
   every real user.
5. **Icon and splash.** Export a 1024×1024 icon from Figma, then
   `flutter_launcher_icons` and `flutter_native_splash` generate every size.
   Both packages are already in `dev_dependencies`.
6. **A working test account for the reviewer.** Omitting it is the single most
   common cause of a first rejection for a login-gated app.
7. **UGC policy (Apple Guideline 1.2).** This app generates AI videos of
   public figures. Apple requires a content filter, a report mechanism, a
   block mechanism, and published terms. Account links to the terms; a real
   "report this clip" path is still needed before submitting.
8. **Crash reporting** (Crashlytics or Sentry) *before* launch. Without it a
   user's crash report is unactionable.

## iOS

The Dart is identical on both platforms and the iOS project is configured
(URL schemes, photo-library usage string, portrait lock, dark appearance).
But **iOS cannot be built on Windows** — that needs Xcode, which is macOS
only. Options: a Mac mini, or a CI service (Codemagic, or a GitHub Actions
`macos-latest` runner) that can build and ship to TestFlight without you
owning a Mac. CI-only works for releasing; debugging an iOS-specific layout
bug with no Mac in front of you does not.

## One permanent consequence

The backend and frontend auto-deploy from `main`. Mobile releases are gated
by store review, and users update on their own schedule — so old app versions
stay in the wild for months. **The API can no longer make breaking changes
freely.** Version the endpoints, or keep every change additive.
