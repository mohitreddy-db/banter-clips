# SEO — how BanterClips appears in Google

Source of truth for search presence. The technical foundation is shipped and
lives in `frontend/`; the parts that need a human with account access are in
[Manual steps](#manual-steps-nobody-can-do-these-from-the-repo) and are still open.

---

## Where each piece lives

| Concern | File |
|---|---|
| Crawl rules, sitemap pointer | `frontend/public/robots.txt` |
| Indexable URL list | `frontend/public/sitemap.xml` |
| Site-wide tags, structured data, no-JS fallback | `frontend/index.html` |
| Per-route title / description / canonical / robots | `frontend/src/lib/seo.js` + a `useSeo()` call in each page |
| Favicon, OG card, logo, PWA icons | `frontend/public/*.png`, `favicon.ico` |
| Regenerating those images | `frontend/scripts/gen-brand-assets.py` |

## The constraint everything else follows from

BanterClips is a client-rendered SPA on Vercel with a catch-all rewrite. Two
consequences drive every decision below:

1. **Every URL returns the same `index.html`.** Google executes JS before
   indexing, so `useSeo()` tags are what search sees. Social scrapers (Slack,
   iMessage, WhatsApp, X) **never** run JS — they only see the static tags in
   `index.html`. Those defaults are therefore written to be accurate for the
   home page rather than left as placeholders, and a shared link to `/privacy`
   will unfurl with the home-page card. Fixing that properly means
   prerendering or SSR; it is not worth it while the legal pages are the only
   non-home indexable URLs.

2. **The rewrite swallows any path that is not a real file.** Before this work
   `/robots.txt`, `/sitemap.xml` and `/favicon.ico` all returned `index.html`
   as `text/html` with a `200`. Vercel checks the filesystem before applying
   rewrites, so putting real files in `public/` is the whole fix — no
   `vercel.json` change was needed. **If you ever add a new crawler-facing
   file, put it in `public/` and verify the content-type, not just the status
   code.** A `200` proves nothing here; every path returns `200`.

## Why the app routes are `noindex` rather than `Disallow`

`/studio`, `/clips`, `/account`, `/pricing` and `/onboarding` sit behind the
`AppShell` auth gate. They emit `noindex, follow` via `useSeo()` and are
deliberately **not** disallowed in `robots.txt`.

A `Disallow` stops Google fetching the page, and a `noindex` it never fetches
is a `noindex` it never honours — anything already indexed would be stranded
there. Let Google crawl them, read the `noindex`, and drop them. Once Search
Console shows them gone from the index, moving them to `Disallow` lines saves
crawl budget. Only `/admin` and `/reset-password` are disallowed outright.

Note `/pricing` is `noindex` **because it is gated**, not because pricing pages
are low value — a crawler only ever gets a redirect to `/signin`. The public
pricing story is the `#pricing` section on the landing page.

## Structured data

`index.html` carries one JSON-LD `@graph` with three nodes:

- **`Organization`** — feeds the brand entity. `logo` must stay a real
  crawlable URL.
- **`WebSite`** — `name` is the field Google reads to print **BanterClips**
  above a result instead of `www.banterclips.com`.
- **`WebApplication`** — category, feature list, and the two real offers
  ($0 Free, $9.99/mo Creator).

Two rules when editing it:

- **JSON-LD is strict JSON.** A `//` or `/* */` comment anywhere inside the
  block invalidates it and Google silently drops the entire graph. Keep notes
  in HTML comments outside the `<script>`.
- **Never add `aggregateRating`, `reviewCount` or offers that are not really
  on sale.** Fabricated review markup is a manual-action risk, and the ratings
  would be a lie besides.

Validate after any change: <https://search.google.com/test/rich-results>

## Regenerating brand images

```bash
cd frontend
pip install pillow
python3 scripts/gen-brand-assets.py     # writes into public/
```

Optionally drop `Manrope-ExtraBold.ttf` / `SpaceGrotesk-Bold.ttf` into
`frontend/scripts/fonts/` (or set `BRAND_FONT_DIR`) so the OG card's wordmark
matches the site's faces; without them it falls back to a system font. The
icons carry no text and are unaffected.

`favicon.ico` ships 16/32/48px in one file — 48 is Google's floor for the
search-result icon, and it must be a real URL. A `data:` URI does not qualify,
which is why the site previously had no icon in search results.

---

## Manual steps (nobody can do these from the repo)

These need account access and are **not** done. In rough priority order:

1. **Verify the domain in Google Search Console** — until then there is no
   index coverage data, no query data, and no way to confirm any of the above
   is working. Add `www.banterclips.com` (and the apex, which 308s to www),
   then submit `https://www.banterclips.com/sitemap.xml`.
2. **Request indexing for `/`** via the URL Inspection tool, and use "View
   crawled page" to confirm Google's rendered HTML contains the real landing
   copy and the JSON-LD.
3. **Fill in `Organization.sameAs`** in `frontend/index.html` with the official
   Instagram / TikTok / X / YouTube profile URLs once they exist. This is the
   single highest-value line still missing — `sameAs` is the strongest signal
   Google has for tying this domain to a brand entity, and it is what
   distinguishes a brand from an unknown domain in the eyes of the knowledge
   graph. It is currently omitted rather than guessed.
4. **Bing Webmaster Tools** — imports directly from Search Console, ~2 minutes,
   and Bing renders JS far less reliably than Google, so the static fallback in
   `index.html` matters more there.

**Not applicable:** a Google Business Profile. Those are for businesses with a
physical location or a defined service area. A pure SaaS does not qualify, and
listing a home address to force one is against Google's guidelines and a bad
idea regardless.

## The real ceiling

The technical work above makes the site *eligible* to rank properly and fixes
how the brand renders. It does not create demand. **There are exactly three
indexable URLs, and two of them are legal pages** — so the site can realistically
only win searches for "banterclips", which is a term nobody types yet.

Ranking for the terms the product actually serves — *AI sports video generator*,
*turn sports takes into videos*, *AI Reels for sports content* — needs indexable
pages that answer those queries. The cheapest first moves, in order:

1. **A public, ungated `/pricing` marketing page.** The gated one cannot rank.
   This is the highest-intent commercial query a SaaS gets and the site
   currently forfeits it entirely.
2. **Public showcase pages, one per clip** (`/clips/wemby-roof`). The videos
   already exist in Supabase storage with posters and captions, and
   `Landing.jsx` already carries the metadata — this is mostly a routing and
   `VideoObject` markup exercise, not new content work. It also turns every
   shared clip into an indexable landing page.
3. **A handful of use-case pages** — one per sport or per creator type — built
   from copy that already exists in the BRD.

Until at least (1) ships, expect near-zero organic traffic no matter how clean
the metadata is.
