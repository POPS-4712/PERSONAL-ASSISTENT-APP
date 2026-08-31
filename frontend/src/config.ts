/**
 * Runtime configuration. Everything comes from Vite env vars so the *same*
 * build runs locally and on Vercel — only the values differ.
 *
 *   VITE_API_URL   base URL of the FastAPI backend        (required in prod)
 *   VITE_WS_URL    base URL for WebSockets                 (optional, derived)
 *   VITE_APP_ENV   cosmetic environment label             (optional)
 */

const stripTrailingSlash = (u: string): string => u.replace(/\/+$/, "");

const rawApi = import.meta.env.VITE_API_URL?.trim();

export const API_URL = stripTrailingSlash(rawApi || "http://localhost:8080");

function deriveWsUrl(): string {
  const explicit = import.meta.env.VITE_WS_URL?.trim();
  if (explicit) return stripTrailingSlash(explicit);
  try {
    const u = new URL(API_URL);
    u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
    return stripTrailingSlash(u.origin);
  } catch {
    return "ws://localhost:8080";
  }
}

export const WS_URL = deriveWsUrl();

export const APP_ENV = import.meta.env.VITE_APP_ENV?.trim() || (import.meta.env.DEV ? "development" : "production");

export const IS_DEV = import.meta.env.DEV;

/** True when no explicit backend URL was configured (local-dev default). */
export const API_URL_IS_DEFAULT = !rawApi;
