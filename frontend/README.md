# BanterClips web app (frontend)

React SPA for the Phase 1 MVP — landing page, magic-link sign-in, five-step
onboarding (with plan selection), Create Studio, My Clips, Account, and
Plans & Pricing. Talks to the FastAPI backend (`../backend`) for everything;
nothing is faked client-side except the pace of the Stripe checkout beat.

## Tech stack

- **React 18** + **react-router-dom 7** (BrowserRouter, clean URLs)
- **Vite 6** (`@vitejs/plugin-react`)
- **Tailwind CSS 4** (`@tailwindcss/vite`) + hand-rolled CSS variables for the
  two themes:
  - Landing: the client's slim-MVP design, ported verbatim (Manrope/Space
    Grotesk, blue→green gradient) — client non-negotiable #4
  - App: the Figma navy/cyan theme (#0B0F1C bg, #22D3EE cyan, #34E27A green)
- **puppeteer-core** (dev-only) for headless E2E smoke runs

## Run

```bash
npm install
npm run dev        # http://localhost:5173 — expects the API on :8000
npm run build      # production build into dist/
```

`VITE_API_URL` (see `.env.example`) points at the backend; defaults to
`http://localhost:8000`.

## Structure

```
src/
├── main.jsx               BrowserRouter + AppProvider
├── App.jsx                Routes: / /signin /onboarding + app shell routes
├── lib/api.js             API client (JWT header, typed errors, download helper)
├── state/AppContext.jsx   Session, user, usage, clips, socials + all actions
├── components/
│   ├── AppShell.jsx       Sidebar + topbar + auth guard for app pages
│   └── Modals.jsx         UpgradeModal (mock Stripe) · PublishModal (real API)
└── pages/
    ├── Landing.jsx        Client's landing, faithful port
    ├── SignIn.jsx         Magic link (auto-resolves in DEV_MODE)
    ├── Onboarding.jsx     5 skippable steps: sports → teams/players → role
    │                      → connect socials → pick your plan
    ├── Studio.jsx         Hero create page → honest generation stages
    │                      (server-polled) → result with publish/download
    ├── Clips.jsx          Grid of server clips; retry failed, live progress
    ├── Account.jsx        Profile, plan/usage, connected accounts, prefs
    └── Pricing.jsx        Two-plan comparison + upgrade
```

## Plan gating (client non-negotiables)

Derived in `AppContext` from the server's `/me/usage`:

- **Free** → publish-only, watermark always, download locked (opens the
  upgrade modal). Every free publish is the marketing engine.
- **Creator ($9.99/mo)** → HD download and publishing without the watermark,
  30 videos/month.
- Tones are exactly **Funny / Savage / Hype**.

## Deploying to Vercel

- Project root: `frontend/`
- Build command `npm run build`, output `dist/` (Vite defaults)
- Env var: `VITE_API_URL=https://<backend-domain>`
- `vercel.json` rewrites all routes to `index.html` for the SPA router
