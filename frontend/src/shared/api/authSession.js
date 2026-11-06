import { apiRefreshSession } from "./authApi.js";
import { normalizeAuthUser } from "../context/authRoles.js";

export const AUTH_STORAGE_KEY = "finmind_auth_session";
export const AUTH_CHANGED_EVENT = "finmind:auth-changed";
const refreshes = new WeakMap();

export function readAuthSession(storage = globalThis.localStorage) {
  try {
    const session = JSON.parse(storage.getItem(AUTH_STORAGE_KEY) || "null");
    if (!session || typeof session.token !== "string" || !session.token.trim()) return null;
    return { ...session, isExpired: typeof session.expiresAtTimestamp === "number" && Date.now() >= session.expiresAtTimestamp };
  } catch { return null; }
}

export function authChanged() {
  if (typeof window !== "undefined") window.dispatchEvent(new Event(AUTH_CHANGED_EVENT));
}

export function sessionError() {
  const error = new Error("Phiên đăng nhập không còn hợp lệ. Vui lòng đăng nhập lại.");
  error.status = 401;
  return error;
}

export function refreshStoredSession(snapshot, { storage = globalThis.localStorage, refresh = apiRefreshSession, notify = authChanged, locks = globalThis.navigator?.locks } = {}) {
  if (!storage || !snapshot?.refreshToken) return Promise.reject(sessionError());
  let pending = refreshes.get(storage);
  if (!pending) { pending = new Map(); refreshes.set(storage, pending); }
  if (pending.has(snapshot.refreshToken)) return pending.get(snapshot.refreshToken);
  const execute = async () => {
    const current = readAuthSession(storage);
    if (!current?.refreshToken) throw sessionError();
    // Another tab already rotated this token or signed into a new session.
    if (current.refreshToken !== snapshot.refreshToken && !current.isExpired) return current;
    let response;
    try { response = await refresh(current.refreshToken); }
    catch (error) {
      if ([401, 403, 422].includes(error.status) && readAuthSession(storage)?.refreshToken === current.refreshToken) {
        storage.removeItem(AUTH_STORAGE_KEY); notify();
      }
      throw error;
    }
    const latest = readAuthSession(storage);
    // A late response must never undo logout or overwrite a newer login.
    if (!latest) throw sessionError();
    if (latest.refreshToken !== current.refreshToken) return latest;
    if (typeof response?.access_token !== "string" || !response.access_token.trim() || typeof response.refresh_token !== "string" || !response.refresh_token.trim() || !Number.isFinite(response.expires_in) || !(response.expires_in > 0)) throw sessionError();
    const now = Date.now(), expiresAtTimestamp = now + response.expires_in * 1000;
    const profile = response.user ? { ...current.user, id: response.user.user_id, email: response.user.email, name: response.user.full_name, roles: response.user.roles } : current.user;
    const next = { ...current, user: normalizeAuthUser(profile), token: response.access_token, refreshToken: response.refresh_token,
      expiresAtTimestamp, expiresAt: new Date(expiresAtTimestamp).toISOString(), isExpired: false };
    storage.setItem(AUTH_STORAGE_KEY, JSON.stringify(next)); notify(); return next;
  };
  // Web Locks serialize rotation across browser tabs; the promise also prevents
  // duplicate refreshes during React StrictMode and simultaneous API requests.
  const promise = (locks?.request ? locks.request("finmind-session-refresh", execute) : execute())
    .finally(() => pending.delete(snapshot.refreshToken));
  pending.set(snapshot.refreshToken, promise);
  return promise;
}
