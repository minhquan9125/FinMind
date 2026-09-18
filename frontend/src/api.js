// Thin fetch wrapper around the FastAPI backend (backend/src routers).
// Base URL is injected at build/dev time via VITE_API_BASE_URL (see .env.local).

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request(path, options) {
  const response = await fetch(`${API_BASE_URL}${path}`, options);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch {
      // response body was not JSON - keep statusText
    }
    throw new Error(detail);
  }
  return response.json();
}

export function uploadDocument(file) {
  const formData = new FormData();
  formData.append("file", file);
  return request("/api/documents", { method: "POST", body: formData });
}

export function getChunkDetails(documentId) {
  return request(`/api/documents/${documentId}/chunks`);
}

export function getVocab(documentId, query = "") {
  const params = query ? `?q=${encodeURIComponent(query)}` : "";
  return request(`/api/documents/${documentId}/vocab${params}`);
}

export function searchDocument(documentId, query, topK) {
  return request("/api/search", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ document_id: documentId, query, top_k: topK }),
  });
}
