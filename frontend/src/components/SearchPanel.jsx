import { useState } from "react";
import { searchDocument } from "../api.js";

function escapeRegExp(term) {
  return term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function highlight(text, terms) {
  if (!terms || !terms.length) return text;
  const pattern = new RegExp(`(${terms.map(escapeRegExp).join("|")})`, "giu");
  const parts = text.split(pattern);
  return parts.map((part, i) =>
    terms.some((t) => t.toLowerCase() === part.toLowerCase()) ? (
      <mark key={i}>{part}</mark>
    ) : (
      <span key={i}>{part}</span>
    )
  );
}

export default function SearchPanel({ documentId }) {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(5);
  const [results, setResults] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  async function runSearch() {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const data = await searchDocument(documentId, query.trim(), topK);
      setResults(data.results);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-white border border-border rounded-2xl p-4.5 mb-4">
      <h2 className="text-sm font-semibold mb-2.5">2. Search relevant chunks (Vector Search)</h2>
      <div className="flex gap-2.5 flex-wrap items-center">
        <input
          type="text"
          className="flex-1 min-w-[180px] px-3 py-2.5 border border-border rounded-lg text-[13.5px]"
          placeholder="Enter a question or keywords to search in the document..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
        />
        <select
          className="px-2.5 py-2 border border-border rounded-lg text-[13px] bg-white"
          value={topK}
          onChange={(e) => setTopK(Number(e.target.value))}
        >
          <option value={3}>Top 3</option>
          <option value={5}>Top 5</option>
          <option value={10}>Top 10</option>
        </select>
        <button
          onClick={runSearch}
          disabled={loading}
          className="bg-brand hover:bg-brand-dark disabled:opacity-50 text-white rounded-lg px-4 py-2.5 text-[13.5px] font-semibold"
        >
          Search
        </button>
      </div>
      <div className="text-[11.5px] text-muted mt-2.5 leading-relaxed">
        Score % is the cosine similarity between the query's BAAI/bge-m3 embedding and each chunk's embedding,
        computed by pgvector (embedding &lt;=&gt; embedding) - the higher, the more semantically related.
      </div>

      {error && <div className="text-red-600 text-[12.5px] mt-2">Error: {error}</div>}

      <div className="mt-2.5">
        {results && results.length === 0 && (
          <div className="text-muted text-[12.5px] text-center py-3.5">
            No related chunk found - try different keywords.
          </div>
        )}
        {results &&
          results.map((r) => {
            const pct = Math.min(100, Math.round(r.score * 100));
            return (
              <div className="border border-border rounded-xl p-3.5 mt-2.5" key={r.chunk_index}>
                <div className="flex justify-between items-baseline mb-1.5 gap-2.5">
                  <span className="text-[11.5px] text-muted">Page {r.page}</span>
                  <span className="text-[11.5px] text-brand-dark font-semibold">{pct}% similar</span>
                </div>
                <div className="h-[5px] rounded-full bg-border overflow-hidden mb-2.5">
                  <span className="block h-full bg-brand rounded-full" style={{ width: `${pct}%` }} />
                </div>
                <div className="text-[13px] leading-relaxed whitespace-pre-wrap">
                  {highlight(r.text, r.matched_terms)}
                </div>
              </div>
            );
          })}
      </div>
    </div>
  );
}
