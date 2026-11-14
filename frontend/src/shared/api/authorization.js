// The auth context stores the current access token under this key.
export function authorizedHeaders(headers = {}) {
  try {
    const token = JSON.parse(localStorage.getItem("finmind_auth_session") || "null")?.token;
    return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
  } catch {
    return headers;
  }
}
import { readAuthSession, refreshStoredSession, sessionError, authChanged, AUTH_STORAGE_KEY } from "./authSession.js";


export async function authorizedFetch(url, options = {}) {
  let session = readAuthSession();
  if (!session) { authChanged(); throw sessionError(); }
  if (session.isExpired && session.refreshToken) session = await refreshStoredSession(session);
  let usedToken = session.token;
  const send = token => {
    usedToken = token;
    const headers = new Headers(options.headers || {});
    headers.set("Authorization", `Bearer ${token}`);
    return fetch(url, { ...options, headers });
  };
  let response = await send(session.token);
  if (response.status === 401) {
    const latest = readAuthSession();
    if (!latest) { authChanged(); throw sessionError(); }
    if (latest.token !== session.token) response = await send(latest.token);
    else if (latest.refreshToken) response = await send((await refreshStoredSession(latest)).token);
    if (response.status === 401) {
      // Only expire the session that this request actually used.
      if (readAuthSession()?.token === usedToken) {
        // An invalid refreshed token also requires signing in again.
        localStorage.removeItem(AUTH_STORAGE_KEY); authChanged();
      }
      throw sessionError();
    }
  }
  return response;
}
