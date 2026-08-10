# BanterClips web app (frontend)

React SPA for the Phase 1 MVP ([`../BRD.md`](../BRD.md)) — landing, real
Supabase sign-up/sign-in, five-step onboarding (incl. plan pick), Create
Studio, My Clips, Account, Plans & Pricing. All data comes from the FastAPI
backend; nothing user-facing is faked client-side except the pacing of the
mock Stripe checkout beat.

**Prod:** https://www.banterclips.com (Vercel, auto-deploys `main`).

## Tech stack

| Layer | Choice |
|---|---|
| Framework | React 18 + react-router-dom 7 (BrowserRouter, clean URLs) |
| Build | Vite 6 (`@vitejs/plugin-react`) |
| Styling | Tailwind CSS 4 (`@tailwindcss/vite`) + CSS variables, two themes: client's landing theme (verbatim port — non-negotiable #4) and the app's navy/cyan theme |
| Auth | `@supabase/supabase-js` → token exchanged for an API session (`src/lib/api.js`) |
| E2E (dev-only) | puppeteer-core driving system Chrome |

## Local setup

```bash
npm install
cp .env.example .env    # pick local vs prod API inside — see the file
npm run dev             # → http://localhost:5173
```

Prereq for the default (local API) config: the backend running on :8000 —
see [`../backend/README.md`](../backend/README.md). Point `VITE_API_URL` at
`https://api.banterclips.com` instead to develop against prod data (CORS
already allows localhost).

`npm run build` → production bundle in `dist/` (what Vercel runs).

## Environment — local vs prod

| Variable | Local | Prod (set in Vercel dashboard) |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` (or prod API) | `https://api.banterclips.com` |
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` | same as prod (anon key is browser-safe) | same |

Vite inlines env at **build time** — restart the dev server / redeploy after
changes. Both empty Supabase vars → app falls back to the instant dev
magic-link (needs local backend with `DEV_MODE=true`).

## Structure

```
src/
├── main.jsx               BrowserRouter + AppProvider
├── App.jsx                Routes: / /signin /onboarding + app-shell routes
├── lib/
│   ├── api.js             API client — JWT header, typed errors, blob download
│   └── supabase.js        Supabase Auth client (+ `supabaseEnabled` flag)
├── state/AppContext.jsx   Session, user, usage, clips, socials + all actions
├── components/
│   ├── AppShell.jsx       Sidebar/topbar layout + auth guard
│   └── Modals.jsx         UpgradeModal (mock Stripe) · PublishModal (real API + status polling)
└── pages/
    ├── Landing.jsx        Client's landing page, faithful port
    ├── SignIn.jsx         Sign in / Create account tabs + magic-link option
    ├── Onboarding.jsx     5 skippable steps: sports → teams/players → role → connect → plan
    ├── Studio.jsx         Hero create page → live generation stages → result
    ├── Clips.jsx          Server clip grid; live progress, retry, publish, download
    ├── Account.jsx        Profile, plan/usage, connected accounts, preferences
    └── Pricing.jsx        Two-plan comparison + upgrade
```

## Plan gating (client non-negotiables)

Derived in `AppContext` from the server's `/me/usage` — the server enforces,
the client mirrors:

- **Free** → publish-only, watermark always, download locked (locked button =
  the upgrade prompt, per BR-08). Video players strip browser download
  affordances (`controlsList="nodownload"`, no PiP, no context menu).
- **Creator ($9.99/mo)** → HD download + watermark-free publishing, 30/mo.
- Tones are exactly **Funny / Savage / Hype**.

## Deploying

Push to `main` → Vercel builds `frontend/` and deploys. Domains, env vars,
and the Vercel project details live in `infra/PROD.md` (gitignored).
