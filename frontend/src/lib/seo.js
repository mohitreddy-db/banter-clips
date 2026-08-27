import { useEffect } from "react";

/* Per-route <head> management.
 *
 * This is a client-rendered SPA, so every URL is served the same index.html.
 * Without this, /privacy and /terms would inherit the home page's title,
 * description and canonical — Google reads those as three near-duplicates of
 * one page and keeps whichever it likes. Google does execute JS before
 * indexing, so the tags written here are the ones that count for search.
 *
 * Social scrapers (Slack, iMessage, WhatsApp, X) do NOT execute JS — they only
 * ever see the static tags in index.html. That is a known limitation of CSR and
 * the reason index.html carries a complete, home-page-accurate default set
 * rather than placeholders.
 */

export const SITE_URL = "https://www.banterclips.com";
export const SITE_NAME = "BanterClips";
const DEFAULT_IMAGE = `${SITE_URL}/og.png`;

/** Find-or-create a <meta>, then set its content. Idempotent, so StrictMode's
 *  double-invoked effects and repeat navigations cannot stack duplicate tags. */
function meta(keyAttr, keyValue, content) {
  if (content == null) return;
  const sel = `meta[${keyAttr}="${keyValue}"]`;
  let el = document.head.querySelector(sel);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(keyAttr, keyValue);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content);
}

function canonical(href) {
  let el = document.head.querySelector('link[rel="canonical"]');
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", "canonical");
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

/**
 * @param {object}  o
 * @param {string}  o.title        Full <title>. Keep under ~60 chars or Google
 *                                 truncates it mid-word in the result.
 * @param {string}  o.description  Keep to ~150-160 chars, same reason.
 * @param {string} [o.path]        Canonical path, e.g. "/privacy". Defaults to
 *                                 the current pathname. Pass it explicitly on
 *                                 routes that can carry query params, so the
 *                                 canonical never points at "?token=..." .
 * @param {boolean}[o.noindex]     True for anything behind the auth gate.
 * @param {string} [o.image]       Absolute URL; defaults to the site OG card.
 */
export function useSeo({ title, description, path, noindex = false, image = DEFAULT_IMAGE }) {
  useEffect(() => {
    const url = `${SITE_URL}${path ?? window.location.pathname}`.replace(/\/+$/, "") || SITE_URL;
    // Trailing slash only on the root, so "/" and "" cannot both be canonical.
    const href = url === SITE_URL ? `${SITE_URL}/` : url;

    if (title) document.title = title;
    meta("name", "description", description);
    canonical(href);

    meta(
      "name",
      "robots",
      noindex
        ? // `follow` still lets link equity flow out of a gated page; only the
          // page itself is kept out of the index.
          "noindex, follow"
        : "index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1"
    );

    meta("property", "og:title", title);
    meta("property", "og:description", description);
    meta("property", "og:url", href);
    meta("property", "og:image", image);
    meta("name", "twitter:title", title);
    meta("name", "twitter:description", description);
    meta("name", "twitter:image", image);
  }, [title, description, path, noindex, image]);
}

/**
 * Route-scoped JSON-LD. The site-wide graph (Organization/WebSite/
 * WebApplication) lives statically in index.html; this hook is for structured
 * data that only makes sense on one route — e.g. the VideoObject on a
 * /showcase/:slug page. One managed <script> per `id`; replaced when `data`
 * changes, removed when the route unmounts so it can't leak onto other pages.
 *
 * `data` must be JSON-serializable and TRUE of the page — same rules as the
 * static graph: no invented ratings, dates or reviews.
 */
export function useJsonLd(id, data) {
  useEffect(() => {
    if (!data) return undefined;
    const attr = "data-route-jsonld";
    let el = document.head.querySelector(`script[${attr}="${id}"]`);
    if (!el) {
      el = document.createElement("script");
      el.type = "application/ld+json";
      el.setAttribute(attr, id);
      document.head.appendChild(el);
    }
    el.textContent = JSON.stringify(data);
    return () => el.remove();
  }, [id, JSON.stringify(data)]);
}
