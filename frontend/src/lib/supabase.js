// Supabase Auth client — handles signup/sign-in (real emails, real passwords).
// After Supabase authenticates, AppContext exchanges the Supabase access token
// for a BanterClips API session via POST /auth/supabase.

import { createClient } from "@supabase/supabase-js";

const url = import.meta.env.VITE_SUPABASE_URL;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY;

export const supabaseEnabled = Boolean(url && anonKey);

// Captured BEFORE supabase-js consumes (and strips) the URL hash: a password
// recovery link landed us here, wherever "here" is.
export const urlIsPasswordRecovery =
  typeof window !== "undefined" && window.location.hash.includes("type=recovery");

export const supabase = supabaseEnabled
  ? createClient(url, anonKey, { auth: { persistSession: true, autoRefreshToken: true } })
  : null;
