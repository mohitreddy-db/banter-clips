import { useEffect, useRef, useState } from "react";
import { api } from "./api.js";

/**
 * Shared trending-feed access. The server keeps one 20-minute cache per
 * sport; this adds a session cache so switching sports back and forth never
 * refetches or flashes a spinner within that window, and a sequence guard
 * so a slow fetch for the previous sport can never paint over the current
 * one. Key is versioned: the feed gained `presets` for the Viral tab.
 */

const CLIENT_TTL_MS = 20 * 60 * 1000;
const cacheKey = (sport) => `bc-trending-v2-${sport}`;

export function readCache(sport) {
  try {
    const raw = sessionStorage.getItem(cacheKey(sport));
    if (!raw) return null;
    const { data, at } = JSON.parse(raw);
    return Date.now() - at < CLIENT_TTL_MS ? data : null;
  } catch {
    return null;
  }
}

export function writeCache(sport, data) {
  try {
    sessionStorage.setItem(cacheKey(sport), JSON.stringify({ data, at: Date.now() }));
  } catch { /* storage full/blocked — the server cache still saves us */ }
}

export function agoLabel(iso) {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  return mins < 1 ? "updated just now" : `updated ${mins}m ago`;
}

export function useTrendingFeed(sport) {
  const [feed, setFeed] = useState(() => readCache(sport));
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);
  const seq = useRef(0);

  useEffect(() => {
    const mySeq = ++seq.current;
    const cached = readCache(sport);
    if (cached) {
      setFeed(cached);
      setFailed(false);
      setLoading(false);
      return;
    }
    setFeed(null);
    setFailed(false);
    setLoading(true);
    api
      .trending(sport)
      .then((data) => {
        writeCache(sport, data);
        if (seq.current !== mySeq) return;
        setFeed(data);
      })
      .catch(() => seq.current === mySeq && setFailed(true))
      .finally(() => seq.current === mySeq && setLoading(false));
  }, [sport]);

  return { feed, loading, failed };
}
