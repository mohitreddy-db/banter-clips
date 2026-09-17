# Android test report — status (build 0.3.0+6)

Item-by-item answer to *BanterClips android app – test report*. "Done" means
it is in this build; "Config" means the code is there and a console/dashboard
setting is what makes it work; "Backend" means the server on the droplet must
run the `backend/` code on this branch.

## Authentication

| Item | Status | Notes |
|---|---|---|
| Email magic link not working | **Config** | The link returns to `banterclips://login-callback`. That URI (and `banterclips://reset-password`) must be listed in Supabase → Authentication → URL Configuration → *Redirect URLs*. Until it is, Supabase falls back to the Site URL and the link opens the website instead of the app. The app side (intent filter, PKCE exchange, auth-stream listener) is in place. |
| Auth session expiring too soon | Done (earlier) | A 401 now refreshes the Supabase session and re-exchanges before signing out. |
| `AuthApiException` shown on auth page | Done | Supabase errors are mapped to plain sentences by code (`invalid_credentials`, `email_not_confirmed`, rate limits, …). API errors already came through as human messages. |
| After Google sign-in the landing page shows | Done + Config | Two causes. (1) In-app: the auth deep link lands on path `/`, which used to render the marketing landing while the session was exchanged — `/` now always resolves to sign-in or the product. (2) If Supabase's redirect allow-list is missing the URI above, Google finishes in the browser on banterclips.com; same fix as the magic link. |

## Onboarding

| Item | Status | Notes |
|---|---|---|
| Step 1: more sports | Done | All 13 sports the API accepts, with emoji, 3 per row. |
| Instagram connect redirects to the web | Backend + Config | `backend/app/routers/socials.py` allow-lists `banterclips://oauth/instagram`, `…/tiktok`, `…/youtube` as `next` and bounces back to them. The Meta / TikTok / Google consoles must list the same URIs as valid redirects. |
| Pricing as step 5 | Done | "Pick your plan" with Free / Creator; Creator opens the store paywall and, once the server confirms the plan, finishes setup. |
| Highlight current plan ("✓ Your plan") | Done | Onboarding step 5 and the Pricing screen both show "YOUR PLAN" / "✓ Your plan" for the plan the account is on, "Included in Creator" for Free when on Creator. |
| Other socials on step 4 | Done | "Connect your accounts": Instagram, TikTok, YouTube (live connects) and X (coming soon). |

## Pricing

| Item | Status | Notes |
|---|---|---|
| Shows "Go Creator" while on Creator | Done | Signed-in states mirror the web: Free card → "Current plan" / "Included in Creator", Creator card → "Upgrade to Creator" / "✓ Your plan". Feature lists updated (280 vs 500-char prompts). |

## Create page

| Item | Status | Notes |
|---|---|---|
| Roast tone | Done | Five tones — Funny, Savage, Roast 🔥, Hype, Bold — under STYLE, as on the web. |
| Not all sports present | Done | All 13. |
| Multi-select sports | Done | Up to 4, optional ("we'll work it out from your take"), with Clear. Sent as `sports[]`. |
| Credits line | Done | "⚡ This video: **60 credits** · you have **107** · charged only when your video completes" + "+ Top up credits". The balance turns red when it cannot cover the price. |
| Account PLAN & CREDITS | Done | Wallet, "≈ N videos at 15s Standard (· ≈ M at 15s HD on Creator) · only successful videos charge", Top up, and the plan row exactly as the web. |
| Remove Content Type / Voice / Visual Style / 3 toggles | Done | Gone. The screen now sends only what `ClipCreate` consumes: take, sports, subjects ("Who is in it?"), direction ("What happens?"), reference key, tone, duration, resolution. |

## Hygiene

| Item | Status | Notes |
|---|---|---|
| User-friendly errors everywhere | Done | Auth (above), store billing (Play errors mapped), gallery saves, uploads. |
| Branch-based changes, deploy from `main` only | Done | Everything is on `mobile/test-report-fixes`; nothing was touched on the droplet. See "Questions" below — the repo's backend/frontend are behind the droplet. |

## Bugs

| Item | Status | Notes |
|---|---|---|
| Selected 10 s, got 15 s | **Backend** | The app sends `duration: 10` (verified: `ClipCreate.duration`, stored as `duration_target`). The rendered length is decided by the planner's scene timings in the pipeline, so this is a server-side fix in `backend/app/video/` — not reproducible from the app. |
| Reference image not reaching the backend | Done | It was picked but never uploaded. It now goes to `POST /clips/reference` (raw body, JPEG/MP4 ≤ 15 MB, as the web does) and the returned `reference_key` is sent with the clip. |
| Recent-clips thumbnails missing | Done | Poster frame shown (gradient stays as the fallback for clips made before posters were stored). |
| No download button | Done | Share removed. **Download** saves the MP4 to the gallery ("BanterClips" album) via the `gal` package; Creator only — Free sees the locked button and the paywall, and the server refuses with 403 regardless. |
| Pay button stuck loading after closing the Play sheet | Done | Root cause: Play reports a cancelled checkout with an *empty* product id, and the handler filtered on product id first, so the cancel never reached it. Cancel/error events are now handled first; a 2-minute safety timeout returns the button regardless. |
| Shows ₹2,100 instead of $19 | Done + Config | The button says "Upgrade to Creator — $19/mo"; underneath: "Billed by Google Play as ₹…/month" (the store's own figure). ₹2,100 is what the Play Console pricing template currently sets for India — the app cannot change what Play charges. Set the India price in the Play Console to the $19 equivalent. |
| Paid plan should allow 500 chars | Done + Backend | Counter is 280 on Free (with "up to 500 on Creator →") and 500 on Creator. **Note:** production's `clips.take` column still has a `<= 280` check constraint, so a 300-character take from a Creator fails at the database today; `backend/app/db_migrate.py` on this branch widens it on boot. |
| My Clips header "47/60 left" | Done | "47 ⚡ left" on every plan. |

## Missing things

| Item | Status | Notes |
|---|---|---|
| Top-up credits via Google billing | Done + Backend + Config | Top-up sheet lists `/billing/packs`, prices from the store, buys a **consumable** (`credits_<pack>`), verifies through `POST /billing/mobile/verify`, which grants the credits and consumes the purchase. Backend part is on this branch (`_verify_credit_pack`, `services/credits.py`, `store_purchases` table). The four products must be created in the Play Console as one-time products. |
| Viral tab | Done | Own tab: sports strip (yours first), heat badges, one-tap presets and ready-written takes → Studio with take/tone/length/sport pre-filled, refresh with the server's cooldown. |
| Feedback tab | Done | Own tab → `POST /feedback` (category, message, rating). Also linked from Account → "Report a clip or a problem". |
| TikTok and YouTube publishing | Done | Publish sheet has a platform picker. TikTok: creator-info, who-can-view, comment/duet/stitch, disclosure (brand organic / branded content), unaudited notice, legal line. YouTube: title (100 chars), description (5000 bytes), visibility, API-services line. Instagram unchanged. |

## Questions

**Payments — Stripe or Google Play?** Both, by surface. Digital goods bought
inside the app (the Creator subscription, credit packs) must go through
Google Play / Apple — a Stripe page opened from the app is a store-policy
rejection. The website keeps Stripe. The server verifies each receipt with
the store it came from and is the only thing that changes the plan or the
wallet.

**Backend deployment.** No changes were made on the droplet. Everything is
on the branch. **Important before rolling back:** the droplet is running
code that is *not in the repository* — credits/wallet, top-ups, `/feedback`,
`/clips/reference`, TikTok/YouTube OAuth, multi-sport clips, the viral feed,
and the matching web pages exist on `api.banterclips.com` /
`banterclips.com` but not in `backend/` or `frontend/src` on `main`. Rolling
the droplet back to the repo's `main` would remove all of that from the
website. The order that works: copy the droplet's current `backend/` and
`frontend/` into the repo on a branch first (that becomes the new baseline),
then merge this branch's backend changes on top (they are small and
self-contained: `routers/billing.py`, `routers/socials.py`,
`services/store_billing.py`, `services/credits.py`, `models.py`,
`db_migrate.py`). `services/credits.py` here mirrors the production ledger
(`users.credits` + `credit_entries`, kind `topup`, note `pack <key>`); on
the droplet's codebase, point `grant_topup` at the existing ledger function
instead.

## Checklist

| Item | Status |
|---|---|
| Privacy and Terms as per web | Done — the site's text verbatim (effective Sept 12 2026) in `features/public/legal_text.dart`. |
| Download only for paid users | Done — client gate + server 403; Free renders are watermarked server-side. |

## Pending

| Item | Status |
|---|---|
| Admin console | Unchanged (read-only summary screen; not a priority). |
