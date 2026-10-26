// The auth context stores the current access token under this key.
export function authorizedHeaders(headers = {}) {
  try {
    const token = JSON.parse(localStorage.getItem("finmind_auth_session") || "null")?.token;
    return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
  } catch {
    return headers;
  }
}
